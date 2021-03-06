import os
from requests import Session, Timeout
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError
from urllib3.util import Retry
from newreleases.errors import (
    HttpClientError,
    HttpClientTimeout,
    HttpRateLimitExceeded,
)


class HttpClient:
    """Generic requests handler.

    Handles retries and HTTP errors.
    """

    ERRORS = {
        401: "Unauthorized",
        403: "Forbidden!",
        404: "Not found.",
        429: "NewReleases under pressure! (Too many requests)",
        500: "You broke NewReleases!!!",
        502: "NewReleases server not reachable.",
        503: "NewReleases server under maintenance.",
    }

    def __init__(
        self,
        url,
        auth_key=None,
        timeout=60,
        max_retries=3,
        backoff_factor=0.05,
        backoff_max=10,
        status_forcelist=(500, 502, 503, 504),
    ):
        """Initialize.

        Args:
            url (str): URL to the NewReleases server.
            auth_key (str): NewReleases Auth key.
            timeout (int): Request timeout time.
            max_retries (int): Maximal number of retries.
            backoff_factor (float): Backoff factor.
            status_forcelist (tuple of int): Tuple of HTTP statuses for
                which the service should retry.
        """
        self.url = url
        self.auth_key = auth_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.backoff_max = backoff_max
        self.status_forcelist = status_forcelist

        # Setup headers
        self.headers = {"Content-Type": "application/json"}
        if self.auth_key is not None:
            self.headers["X-Key"] = self.auth_key

        self.response = None

        # setup connection pool
        self.session = Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        retry.BACKOFF_MAX = backoff_max
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount(self.url, adapter)

    def request(
        self, method, url, headers=None, params=None, data=None, timeout=None
    ):
        """Request method.

        Request method handles all the url joining, header merging, logging and
        error handling.

        Args:
            method (str): Method for the request - GET or POST
            url (str): Partial url of the request. It is added to the base url
            headers (dict): Dictionary of additional HTTP headers
            params (dict): Dictionary of query parameters for the request
            data (dict): A JSON serializable Python object to send in the body
                of the request. Used only in POST requests.
            timeout (float): How many seconds to wait for the server to send
                data before giving up
        """
        full_url = os.path.join(self.url, url.strip("/"))
        headers = {**self.headers, **(headers or {})}
        timeout = timeout or self.timeout

        try:
            if method.lower() == "get":
                self.response = self.session.get(
                    url=full_url,
                    headers=headers,
                    params=params,
                    timeout=timeout,
                )
            elif method.lower() == "post":
                self.response = self.session.post(
                    url=full_url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=timeout,
                )
            elif method.lower() == "delete":
                self.response = self.session.delete(
                    url=full_url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=timeout,
                )
            else:
                raise HttpClientError(f"Unsupported method: {method}")
        except Timeout as e:
            # If request timed out, let upper level handle it they way it sees
            # fit one place might want to retry another might not.
            raise HttpClientTimeout(from_error=e)

        except ConnectionError as e:
            raise HttpClientError(
                f"NewReleases server not reachable.", from_error=e
            )

        except Exception as e:
            raise HttpClientError(f"Unknown error: {e}", from_error=e)

        if self.response.status_code == 200:
            try:
                return self.response.json() if self.response.text else {}
            except Exception as e:
                raise HttpClientError(
                    f"Error while parsing server response: {e}",
                    response=self.response,
                    from_error=e,
                )
        # Check rate limit
        limit = self.response.headers.get("X-Ratelimit-Limit", None)
        if limit is not None:
            remaining = self.response.headers["X-Ratelimit-Remaining"]
            reset = self.response.headers["X-Ratelimit-Reset"]
            retry = self.response.headers["X-Ratelimit-Retry"]

            if remaining == 0:
                raise HttpRateLimitExceeded(
                    response=self.response,
                    limit=limit,
                    remaining=remaining,
                    reset=reset,
                    retry=retry,
                )

        # Try known error messages
        message = self.ERRORS.get(self.response.status_code, None)
        if message is not None:
            raise HttpClientError(message, response=self.response)

        if self.response.status_code == 400:
            try:
                message = "\n".join(self.response.json()["errors"])
            except Exception:
                message = "Bad Request."
            raise HttpClientError(message, response=self.response)

        # Generalize unknown messages.
        try:
            message = self.response.json()["message"]
        except Exception:
            message = "Unknown error."
        raise HttpClientError(message, response=self.response)

    def get(self, url, headers=None, params=None, timeout=None):
        """Perform get request.

        Args:
            url (str): Partial url of the request. It is added to the base url
            headers (dict): Dictionary of additional HTTP headers
            params (dict): Dictionary of query parameters for the request
            timeout (float): How many seconds to wait for the server to send
                data before giving up

        Returns
            dict: Deserialized json response

        """
        return self.request(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

    def post(self, url, headers=None, params=None, data=None, timeout=None):
        """Perform post request.

        Args:
            url (str): Partial url of the request. It is added to the base url
            headers (dict): Dictionary of additional HTTP headers
            params (dict): Dictionary of query parameters for the request
            data (dict): A JSON serializable Python object to send in the body
                of the request.
            timeout (float): How many seconds to wait for the server to send
                data before giving up

        Returns
            dict: Deserialized json response

        """
        return self.request(
            method="POST",
            url=url,
            headers=headers,
            params=params,
            data=data,
            timeout=timeout,
        )

    def delete(self, url, headers=None, params=None, data=None, timeout=None):
        """Perform delete request.

        Args:
            url (str): Partial url of the request. It is added to the base url
            headers (dict): Dictionary of additional HTTP headers
            params (dict): Dictionary of query parameters for the request
            data (dict): A JSON serializable Python object to send in the body
                of the request.
            timeout (float): How many seconds to wait for the server to send
                data before giving up

        Returns
            dict: Deserialized json response
        """
        return self.request(
            method="DELETE",
            url=url,
            headers=headers,
            params=params,
            data=data,
            timeout=timeout,
        )

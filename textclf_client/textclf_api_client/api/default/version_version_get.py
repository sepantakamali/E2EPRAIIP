from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.version_version_get_response_version_version_get import VersionVersionGetResponseVersionVersionGet
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    model: Union[None, Unset, str] = UNSET,
    model_path: Union[None, Unset, str] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_model: Union[None, Unset, str]
    if isinstance(model, Unset):
        json_model = UNSET
    else:
        json_model = model
    params["model"] = json_model

    json_model_path: Union[None, Unset, str]
    if isinstance(model_path, Unset):
        json_model_path = UNSET
    else:
        json_model_path = model_path
    params["model_path"] = json_model_path

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/version",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[HTTPValidationError, VersionVersionGetResponseVersionVersionGet]]:
    if response.status_code == 200:
        response_200 = VersionVersionGetResponseVersionVersionGet.from_dict(response.json())

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Union[HTTPValidationError, VersionVersionGetResponseVersionVersionGet]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    model: Union[None, Unset, str] = UNSET,
    model_path: Union[None, Unset, str] = UNSET,
) -> Response[Union[HTTPValidationError, VersionVersionGetResponseVersionVersionGet]]:
    """Version

    Args:
        model (Union[None, Unset, str]): Resolve metadata for a specific selector: pointer
            ("latest"/"stable"), model_id, or artifact filename.
        model_path (Union[None, Unset, str]): Explicit artifact path (overrides 'model').

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[HTTPValidationError, VersionVersionGetResponseVersionVersionGet]]
    """

    kwargs = _get_kwargs(
        model=model,
        model_path=model_path,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    model: Union[None, Unset, str] = UNSET,
    model_path: Union[None, Unset, str] = UNSET,
) -> Optional[Union[HTTPValidationError, VersionVersionGetResponseVersionVersionGet]]:
    """Version

    Args:
        model (Union[None, Unset, str]): Resolve metadata for a specific selector: pointer
            ("latest"/"stable"), model_id, or artifact filename.
        model_path (Union[None, Unset, str]): Explicit artifact path (overrides 'model').

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[HTTPValidationError, VersionVersionGetResponseVersionVersionGet]
    """

    return sync_detailed(
        client=client,
        model=model,
        model_path=model_path,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    model: Union[None, Unset, str] = UNSET,
    model_path: Union[None, Unset, str] = UNSET,
) -> Response[Union[HTTPValidationError, VersionVersionGetResponseVersionVersionGet]]:
    """Version

    Args:
        model (Union[None, Unset, str]): Resolve metadata for a specific selector: pointer
            ("latest"/"stable"), model_id, or artifact filename.
        model_path (Union[None, Unset, str]): Explicit artifact path (overrides 'model').

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[HTTPValidationError, VersionVersionGetResponseVersionVersionGet]]
    """

    kwargs = _get_kwargs(
        model=model,
        model_path=model_path,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    model: Union[None, Unset, str] = UNSET,
    model_path: Union[None, Unset, str] = UNSET,
) -> Optional[Union[HTTPValidationError, VersionVersionGetResponseVersionVersionGet]]:
    """Version

    Args:
        model (Union[None, Unset, str]): Resolve metadata for a specific selector: pointer
            ("latest"/"stable"), model_id, or artifact filename.
        model_path (Union[None, Unset, str]): Explicit artifact path (overrides 'model').

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[HTTPValidationError, VersionVersionGetResponseVersionVersionGet]
    """

    return (
        await asyncio_detailed(
            client=client,
            model=model,
            model_path=model_path,
        )
    ).parsed

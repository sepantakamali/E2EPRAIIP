from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.model_state_pointer import ModelStatePointer
from ..types import UNSET, Unset

T = TypeVar("T", bound="ModelState")


@_attrs_define
class ModelState:
    """
    Attributes:
        model_path (str):
        pointer (ModelStatePointer):
        meta_version (Union[None, Unset, str]):
        meta_created_at (Union[None, Unset, str]):
    """

    model_path: str
    pointer: ModelStatePointer
    meta_version: Union[None, Unset, str] = UNSET
    meta_created_at: Union[None, Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        model_path = self.model_path

        pointer = self.pointer.value

        meta_version: Union[None, Unset, str]
        if isinstance(self.meta_version, Unset):
            meta_version = UNSET
        else:
            meta_version = self.meta_version

        meta_created_at: Union[None, Unset, str]
        if isinstance(self.meta_created_at, Unset):
            meta_created_at = UNSET
        else:
            meta_created_at = self.meta_created_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "model_path": model_path,
                "pointer": pointer,
            }
        )
        if meta_version is not UNSET:
            field_dict["meta_version"] = meta_version
        if meta_created_at is not UNSET:
            field_dict["meta_created_at"] = meta_created_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        model_path = d.pop("model_path")

        pointer = ModelStatePointer(d.pop("pointer"))

        def _parse_meta_version(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        meta_version = _parse_meta_version(d.pop("meta_version", UNSET))

        def _parse_meta_created_at(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        meta_created_at = _parse_meta_created_at(d.pop("meta_created_at", UNSET))

        model_state = cls(
            model_path=model_path,
            pointer=pointer,
            meta_version=meta_version,
            meta_created_at=meta_created_at,
        )

        model_state.additional_properties = d
        return model_state

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties

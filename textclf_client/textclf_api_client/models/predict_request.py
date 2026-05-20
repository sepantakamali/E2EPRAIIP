from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="PredictRequest")


@_attrs_define
class PredictRequest:
    """
    Attributes:
        texts (list[str]):
        return_probabilities (Union[Unset, bool]):  Default: False.
    """

    texts: list[str]
    return_probabilities: Union[Unset, bool] = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        texts = self.texts

        return_probabilities = self.return_probabilities

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "texts": texts,
            }
        )
        if return_probabilities is not UNSET:
            field_dict["return_probabilities"] = return_probabilities

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        texts = cast(list[str], d.pop("texts"))

        return_probabilities = d.pop("return_probabilities", UNSET)

        predict_request = cls(
            texts=texts,
            return_probabilities=return_probabilities,
        )

        predict_request.additional_properties = d
        return predict_request

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

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
        texts (list[str]): One or more input texts
        return_prob (Union[Unset, bool]): Return class probabilities if available Default: False.
    """

    texts: list[str]
    return_prob: Union[Unset, bool] = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        texts = self.texts

        return_prob = self.return_prob

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "texts": texts,
            }
        )
        if return_prob is not UNSET:
            field_dict["return_prob"] = return_prob

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        texts = cast(list[str], d.pop("texts"))

        return_prob = d.pop("return_prob", UNSET)

        predict_request = cls(
            texts=texts,
            return_prob=return_prob,
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

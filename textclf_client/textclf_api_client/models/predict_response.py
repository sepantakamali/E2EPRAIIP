from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.predict_response_model import PredictResponseModel


T = TypeVar("T", bound="PredictResponse")


@_attrs_define
class PredictResponse:
    """
    Attributes:
        labels (list[int]):
        model (PredictResponseModel):
        probabilities (Union[None, Unset, list[list[float]]]):
    """

    labels: list[int]
    model: "PredictResponseModel"
    probabilities: Union[None, Unset, list[list[float]]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        labels = self.labels

        model = self.model.to_dict()

        probabilities: Union[None, Unset, list[list[float]]]
        if isinstance(self.probabilities, Unset):
            probabilities = UNSET
        elif isinstance(self.probabilities, list):
            probabilities = []
            for probabilities_type_0_item_data in self.probabilities:
                probabilities_type_0_item = probabilities_type_0_item_data

                probabilities.append(probabilities_type_0_item)

        else:
            probabilities = self.probabilities

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "labels": labels,
                "model": model,
            }
        )
        if probabilities is not UNSET:
            field_dict["probabilities"] = probabilities

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.predict_response_model import PredictResponseModel

        d = dict(src_dict)
        labels = cast(list[int], d.pop("labels"))

        model = PredictResponseModel.from_dict(d.pop("model"))

        def _parse_probabilities(data: object) -> Union[None, Unset, list[list[float]]]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                probabilities_type_0 = []
                _probabilities_type_0 = data
                for probabilities_type_0_item_data in _probabilities_type_0:
                    probabilities_type_0_item = cast(list[float], probabilities_type_0_item_data)

                    probabilities_type_0.append(probabilities_type_0_item)

                return probabilities_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list[list[float]]], data)

        probabilities = _parse_probabilities(d.pop("probabilities", UNSET))

        predict_response = cls(
            labels=labels,
            model=model,
            probabilities=probabilities,
        )

        predict_response.additional_properties = d
        return predict_response

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

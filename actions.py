from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal[
        "goto", "click", "fill", "select", "press",
        "wait", "assert", "finish"
    ]
    reason: str = Field(min_length=1)
    element: int | None = Field(default=None, ge=1)
    value: str | None = None
    verdict: Literal["pass", "fail"] | None = None
    evidence: str | None = None
    evidence_type: Literal["text", "url", "element"] | None = None

    @model_validator(mode="after")
    def validate_action(self):
        if not self.reason.strip():
            raise ValueError("reason must not be blank")

        needs_element = self.action in {"click", "fill", "select", "press"}
        if self.action == "assert" and self.evidence_type == "element":
            needs_element = True
        if self.action == "finish" and self.verdict == "pass" and self.evidence_type == "element":
            needs_element = True

        if needs_element and self.element is None:
            raise ValueError("this action requires an element index")
        if not needs_element and self.element is not None:
            raise ValueError("element index is not applicable to this action")

        if self.action in {"goto", "fill", "select", "press"}:
            if self.value is None:
                raise ValueError("this action requires value")
            if self.action != "fill" and not self.value.strip():
                raise ValueError("value must not be blank")
        elif self.value is not None:
            raise ValueError("value is not applicable to this action")

        if (
            self.action != "fill"
            and self.value is not None
            and ("{{" in self.value or "}}" in self.value)
        ):
            raise ValueError("Credential placeholders are only allowed in fill values")

        if self.action == "finish":
            if self.verdict is None:
                raise ValueError("finish requires a verdict")
        elif self.verdict is not None:
            raise ValueError("verdict is only applicable to finish")

        requires_evidence = self.action == "assert" or (
            self.action == "finish" and self.verdict == "pass"
        )
        if requires_evidence:
            if not self.evidence or not self.evidence.strip() or self.evidence_type is None:
                raise ValueError("assert and PASS require evidence and evidence_type")
        elif self.evidence is not None or self.evidence_type is not None:
            raise ValueError("evidence is not applicable to this action")

        return self

"""Bindings for connecting dag nodes to UI elements."""

from dataclasses import dataclass, field
from typing import Any, Optional, Callable
from enum import Enum, auto


class BindingType(Enum):
    """Type of binding between UI and dag node."""

    INPUT = auto()      # User can edit, sets Input node
    OUTPUT = auto()     # Display only, shows computed value
    TWO_WAY = auto()    # Both editable and displays computed value


@dataclass
class Binding:
    """
    Base class for UI bindings to dag nodes.

    A binding connects a dag computed function to a UI element,
    specifying how the value should be displayed and whether
    it can be edited.
    """

    computed_func: Any  # ComputedFunctionDescriptor
    label: Optional[str] = None
    format: Optional[str] = None
    widget_type: Optional[str] = None  # "slider", "input", "dropdown", etc.
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    options: Optional[list[Any]] = None  # For dropdown
    help_text: Optional[str] = None
    binding_type: BindingType = BindingType.OUTPUT

    @property
    def node_path(self) -> str:
        """Get the node path for this binding."""
        # The computed_func has __self__ (model instance) and __name__
        model = getattr(self.computed_func, "__self__", None)
        name = getattr(self.computed_func, "__name__", "unknown")
        if model is not None:
            model_name = getattr(model, "_name", None) or type(model).__name__
            return f"{model_name}.{name}"
        return name

    @property
    def display_label(self) -> str:
        """Get the display label for this binding."""
        if self.label:
            return self.label
        # Get name from descriptor or fallback
        descriptor = getattr(self.computed_func, "_descriptor", None)
        if descriptor:
            name = getattr(descriptor, "name", "Unknown")
        else:
            name = getattr(self.computed_func, "__name__", "Unknown")
        # Convert PascalCase to Title Case
        # Insert space before capitals: TimeToExpiry -> Time To Expiry
        import re
        return re.sub(r"(?<!^)(?=[A-Z])", " ", name)

    def to_dict(self) -> dict:
        """Convert binding to dictionary for serialization."""
        return {
            "node_path": self.node_path,
            "label": self.display_label,
            "format": self.format,
            "widget_type": self.widget_type,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "step": self.step,
            "options": self.options,
            "help_text": self.help_text,
            "binding_type": self.binding_type.name.lower(),
        }


@dataclass
class InputBinding(Binding):
    """Binding for user-editable inputs (requires dag.Input flag)."""

    binding_type: BindingType = field(default=BindingType.INPUT, init=False)


@dataclass
class OutputBinding(Binding):
    """Binding for display-only computed values."""

    binding_type: BindingType = field(default=BindingType.OUTPUT, init=False)


@dataclass
class TwoWayBinding(Binding):
    """Binding for values that are both editable and computed."""

    binding_type: BindingType = field(default=BindingType.TWO_WAY, init=False)


def bind(
    computed_func: Any,
    label: Optional[str] = None,
    format: Optional[str] = None,
    widget_type: Optional[str] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    step: Optional[float] = None,
    options: Optional[list[Any]] = None,
    help_text: Optional[str] = None,
    editable: Optional[bool] = None,
) -> Binding:
    """
    Create a binding between a dag node and a UI element.

    This is the primary API for connecting dag computed functions to UI.
    The binding type is automatically inferred from the node's flags
    unless explicitly specified.

    Args:
        computed_func: The dag computed function to bind (e.g., option.Price)
        label: Display label (defaults to function name as Title Case)
        format: Format string for display:
            - "%" for percentage (value * 100 with % suffix)
            - "$,.2f" for currency
            - ".4f" for 4 decimal places
        widget_type: Preferred widget type ("slider", "input", "dropdown")
        min_value: Minimum value for sliders
        max_value: Maximum value for sliders
        step: Step size for sliders/spinners
        options: List of options for dropdown
        help_text: Tooltip or help text
        editable: Force editable (True) or read-only (False)

    Returns:
        An appropriate Binding subclass based on the node's flags.

    Example:
        bind(option.Spot, label="Spot Price", format="$,.2f")
        bind(option.Volatility, label="Vol", format="%", widget_type="slider",
             min_value=0.01, max_value=1.0, step=0.01)
        bind(option.Price, label="Option Price", format="$,.4f")
    """
    # Determine binding type from flags or explicit setting
    if editable is True:
        binding_type = BindingType.INPUT
    elif editable is False:
        binding_type = BindingType.OUTPUT
    else:
        # Auto-detect from dag flags
        binding_type = _infer_binding_type(computed_func)

    # Create appropriate binding class
    binding_class = {
        BindingType.INPUT: InputBinding,
        BindingType.OUTPUT: OutputBinding,
        BindingType.TWO_WAY: TwoWayBinding,
    }[binding_type]

    return binding_class(
        computed_func=computed_func,
        label=label,
        format=format,
        widget_type=widget_type,
        min_value=min_value,
        max_value=max_value,
        step=step,
        options=options,
        help_text=help_text,
    )


def _infer_binding_type(computed_func: Any) -> BindingType:
    """
    Infer the binding type from a computed function's dag flags.

    Args:
        computed_func: A dag computed function (ComputedFunctionAccessor)

    Returns:
        The appropriate BindingType
    """
    import dag

    # ComputedFunctionAccessor has _descriptor attribute
    descriptor = getattr(computed_func, "_descriptor", None)

    if descriptor is None:
        # Fallback: try to get descriptor from the model class
        model = getattr(computed_func, "_obj", None)
        if model is not None:
            desc_name = getattr(descriptor, "name", None) if descriptor else None
            if desc_name is None:
                # Try to get name from the descriptor if available
                descriptor = getattr(computed_func, "_descriptor", None)
                if descriptor:
                    desc_name = getattr(descriptor, "name", None)
            if desc_name:
                descriptor = getattr(type(model), desc_name, None)

    if descriptor is None:
        return BindingType.OUTPUT

    # ComputedFunctionDescriptor stores flags as 'flags' not '_flags'
    flags = getattr(descriptor, "flags", 0)

    # Check for Input flag
    has_input = bool(flags & dag.Input)
    has_overridable = bool(flags & dag.Overridable)

    if has_input and has_overridable:
        return BindingType.TWO_WAY
    elif has_input:
        return BindingType.INPUT
    else:
        return BindingType.OUTPUT

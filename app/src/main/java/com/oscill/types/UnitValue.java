package com.oscill.types;

import androidx.annotation.NonNull;

import java.util.Locale;

public class UnitValue {

    private final float value;
    private final Unit unit;

    public UnitValue(float value, @NonNull Unit unit) {
        this.value = value;
        this.unit = unit;
    }

    public float getValue(@NonNull Dimension dimension) {
        return unit.getDimension().toDimension(value, dimension);
    }

    public float getValue() {
        return value;
    }

    @NonNull
    @Override
    public String toString() {
        return String.format(Locale.getDefault(),"%.3f", value) + unit.toString();
    }
}

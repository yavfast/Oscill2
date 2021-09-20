package com.oscill;

import androidx.annotation.NonNull;

import com.github.mikephil.charting.components.AxisBase;
import com.github.mikephil.charting.formatter.ValueFormatter;
import com.oscill.types.Unit;

class UnitFormatter extends ValueFormatter {

    protected final Unit unit;

    public UnitFormatter(@NonNull Unit unit) {
        this.unit = unit;
    }

    @Override
    public String getAxisLabel(float value, AxisBase axis) {
        return unit.format(value, 1);
    }
}

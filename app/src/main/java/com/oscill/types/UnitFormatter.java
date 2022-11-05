package com.oscill.types;

import androidx.annotation.NonNull;

import com.github.mikephil.charting.components.AxisBase;
import com.github.mikephil.charting.formatter.IAxisValueFormatter;

public class UnitFormatter implements IAxisValueFormatter {

    protected final Unit unit;

    public UnitFormatter(@NonNull Unit unit) {
        this.unit = unit;
    }

    @Override
    public String getFormattedValue(float value, AxisBase axis) {
        return unit.format(value, 1);
    }
}

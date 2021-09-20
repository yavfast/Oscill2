package com.oscill.types;

import androidx.annotation.NonNull;

import java.text.DecimalFormat;

public class Unit {

    public static final String VOLT = "V";
    public static final String HERZ = "Hz";
    public static final String SECOND = "s";
    public static final String COUNT = "";

    private final Dimension dimension;
    private final String name;

    public Unit(@NonNull Dimension dimension, @NonNull String name) {
        this.dimension = dimension;
        this.name = name;
    }

    @NonNull
    public Dimension getDimension() {
        return dimension;
    }

    @NonNull
    public String format(float value, int precision) {
        if (value == 0f) {
            return decimalFormat.format(0f) + dimension.getPrefix() + name;
        }

        Dimension dimension = Dimension.getDimensionForValue(value);
        float resValue = Dimension.NORMAL.toDimension(value, dimension);
        if (precision == 0) {
            resValue = Math.round(resValue);
        } else {
            float pr = (float) Math.pow(10, precision);
            resValue = ((float) Math.round(resValue * pr)) / pr;
        }

        Dimension resDim = Dimension.getDimension(this.dimension.getMultiplier() + dimension.getMultiplier());
        return decimalFormat.format(resValue) + resDim.getPrefix() + name;
    }

    private final static DecimalFormat decimalFormat = new DecimalFormat("#.####");

    @NonNull
    public String toString() {
        return dimension.getPrefix() + name;
    }
}

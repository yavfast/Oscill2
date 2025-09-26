package com.oscill.types;

import androidx.annotation.NonNull;

import com.oscill.utils.ValueCache;

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
    public String getName() {
        return name;
    }

    public static float round(float value, int precision, @NonNull Dimension dimension) {
        float resValue = Dimension.NORMAL.toDimension(value, dimension);
        if (precision == 0) {
            return Math.round(resValue);
        } else {
            float pr = (float) Math.pow(10, precision);
            return ((float) Math.round(resValue * pr)) / pr;
        }
    }

    @NonNull
    public String format(float value, int precision) {
        if (value == 0f) {
            return decimalFormatCache.get(0f) + dimension.getPrefix() + name;
        }

        Dimension toDimension = Dimension.getDimensionForValue(value);
        float resValue = round(value, precision, toDimension);

        Dimension resDim = Dimension.getDimension(this.dimension.getMultiplier() + toDimension.getMultiplier());
        return decimalFormatCache.get(resValue) + resDim.getPrefix() + name;
    }

    @NonNull
    public String formatFixed(float value, int precision) {
        StringBuilder pattern;
        if (precision > 0) {
            pattern = new StringBuilder("0.");
            for (int i = 0; i < precision; i++) {
                pattern.append("0");
            }
        } else {
            pattern = new StringBuilder("0.#");
        }

        DecimalFormat decimalFormat = new DecimalFormat(pattern.toString());
        if (value == 0f) {
            return decimalFormat.format(0f) + dimension.getPrefix() + name;
        }

        Dimension toDimension = Dimension.getDimensionForValue(value);
        float resValue = round(value, precision, toDimension);

        Dimension resDim = Dimension.getDimension(this.dimension.getMultiplier() + toDimension.getMultiplier());

        return decimalFormat.format(resValue) + resDim.getPrefix() + name;
    }

    private final static DecimalFormat decimalFormat = new DecimalFormat("#.####");

    private final ValueCache<Float, String> decimalFormatCache = new ValueCache<>(decimalFormat::format);

    @NonNull
    public String toString() {
        return dimension.getPrefix() + name;
    }
}

package com.oscill.types;

import androidx.annotation.NonNull;

import com.oscill.utils.ConvertUtils;

public enum Dimension {
    TERA("T", +12),
    GIGA("G", +9),
    MEGA("M", +6),
    KILO("k", +3),
    NORMAL("",0),
    MILLI("m", -3),
    MICRO("µ", -6),
    NANO("n", -9),
    PICO("p", -12);

    private final String prefix;
    private final int multiplier;

    Dimension(@NonNull String prefix, int multiplier) {
        this.prefix = prefix;
        this.multiplier = multiplier;
    }

    @NonNull
    public String getPrefix() {
        return prefix;
    }

    public int getMultiplier() {
        return multiplier;
    }

    @NonNull
    public <V extends Number> V toDimension(@NonNull Number value, @NonNull Dimension target) {
        return toDimension(value, target, (Class<? extends V>) value.getClass());
    }

    @NonNull
    public <V extends Number> V toDimension(@NonNull Number value, @NonNull Dimension target, @NonNull Class<V> targetClass) {
        if (this == target) {
            if (value.getClass() == targetClass) {
                return (V)value;
            }
            return ConvertUtils.convertDoubleTo(value.doubleValue(), targetClass);
        }

        int resMultiplier = multiplier - target.multiplier;
        double res = value.doubleValue() * Math.pow(10, resMultiplier);

        return ConvertUtils.convertDoubleTo(res, targetClass);
    }

    @NonNull
    public static Dimension getDimension(int multiplier) {
        for (Dimension dimension : values()) {
            if (multiplier >= dimension.multiplier) {
                return dimension;
            }
        }
        return PICO;
    }

    @NonNull
    public static Dimension getDimension(@NonNull String dimensionStr) {
        for (Dimension dimension : values()) {
            if (dimensionStr.equals(dimension.prefix)) {
                return dimension;
            }
        }
        return PICO;
    }

    @NonNull
    public static Dimension getDimensionForValue(float value) {
        int multiplier = (int)Math.log10(Math.abs(value));
        return getDimension(multiplier);
    }

}

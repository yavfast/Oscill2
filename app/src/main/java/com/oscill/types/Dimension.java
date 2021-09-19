package com.oscill.types;

import androidx.annotation.NonNull;

public enum Dimension {
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

    public float toDimension(float value, @NonNull Dimension target) {
        if (this == target) {
            return value;
        }
        int resMultiplier = multiplier - target.multiplier;
        return (float) (value * Math.pow(10, resMultiplier));
    }

}

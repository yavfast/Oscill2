package com.oscill.types;

import androidx.annotation.NonNull;

public enum Dimension {
    GIGA("G", 1e+9f),
    MEGA("M", 1e+6f),
    KILO("k", 1e+3f),
    NORMAL("",1f),
    MILLI("m", 1e-3f),
    MICRO("µ", 1e-6f),
    NANO("n", 1e-9f),
    PICO("p", 1e-12f);

    private final String prefix;
    private final float multiplier;

    Dimension(@NonNull String prefix, float multiplier) {
        this.prefix = prefix;
        this.multiplier = multiplier;
    }

    @NonNull
    public String getPrefix() {
        return prefix;
    }

    public float getMultiplier() {
        return multiplier;
    }

    public float toDimension(float value, @NonNull Dimension target) {
        if (this == target) {
            return value;
        }
        return (value * multiplier) / target.multiplier;
    }

}

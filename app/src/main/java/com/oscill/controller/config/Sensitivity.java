package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.types.Dimension;

import static com.oscill.types.Dimension.MILLI;
import static com.oscill.types.Dimension.NORMAL;

public enum Sensitivity {
    _20_mV(20f, MILLI),
    _50_mV(50f, MILLI),
    _100_mV(100f, MILLI),
    _200_mV(200f, MILLI),
    _500_mV(500f, MILLI),
    _1_V(1f, NORMAL),
    _2_V(2f, NORMAL),
    _5_V(5f, NORMAL),
    _10_V(10f, NORMAL);

    private final float value;
    private final Dimension dimension;

    Sensitivity(float value, @NonNull Dimension dimension) {
        this.value = value;
        this.dimension = dimension;
    }

    public float getValue() {
        return value;
    }

    public float getValue(@NonNull Dimension dimension) {
        return Math.round(getDimension().toDimension(value, dimension));
    }

    @NonNull
    public Dimension getDimension() {
        return dimension;
    }

    @NonNull
    public Sensitivity getNext(int step) {
        Sensitivity[] values = values();
        int curIdx = ordinal();
        int newIdx = curIdx + step;
        if (newIdx < 0) {
            newIdx = 0;
        } else if (newIdx >= values.length) {
            newIdx = values.length - 1;
        }
        return values[newIdx];
    }
}

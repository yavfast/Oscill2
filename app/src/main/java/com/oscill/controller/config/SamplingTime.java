package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.types.Dimension;

import static com.oscill.types.Dimension.MICRO;
import static com.oscill.types.Dimension.MILLI;
import static com.oscill.types.Dimension.NANO;

public enum SamplingTime {
    _100_ns(100f, NANO),
    _200_ns(200f, NANO),
    _500_ns(500f, NANO),
    _1_us(1f, MICRO),
    _2_us(2f, MICRO),
    _5_us(5f, MICRO),
    _10_us(10f, MICRO),
    _20_us(20f, MICRO),
    _50_us(50f, MICRO),
    _100_us(100f, MICRO),
    _200_us(200f, MICRO),
    _500_us(500f, MICRO),
    _1_ms(1f, MILLI),
    _2_ms(2f, MILLI),
    _5_ms(5f, MILLI),
    _10_ms(10f, MILLI),
    _20_ms(20f, MILLI),
    _50_ms(50f, MILLI),
    _100_ms(100f, MILLI),
    _200_ms(200f, MILLI),
    _500_ms(500f, MILLI);

    private final float value;
    private final Dimension dimension;

    SamplingTime(float value, @NonNull Dimension dimension) {
        this.value = value;
        this.dimension = dimension;
    }

    public float getValue() {
        return value;
    }

    public float getValue(@NonNull Dimension dimension) {
        return getDimension().toDimension(value, dimension);
    }

    @NonNull
    public Dimension getDimension() {
        return dimension;
    }

    @NonNull
    public SamplingTime getNext(int step) {
        SamplingTime[] values = values();
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

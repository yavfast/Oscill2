package com.oscill.types;

import androidx.annotation.NonNull;

import com.oscill.utils.StringUtils;

public class Range<T> {

    private final T lower;
    private final T upper;

    public Range(@NonNull T lower, @NonNull T upper) {
        this.lower = lower;
        this.upper = upper;
    }

    @NonNull
    public T getLower() {
        return lower;
    }

    @NonNull
    public T getUpper() {
        return upper;
    }

    @NonNull
    @Override
    public String toString() {
        return StringUtils.concat(
                "{",
                "lower: ", String.valueOf(lower),
                "; upper: ", String.valueOf(upper),
                "}");
    }
}

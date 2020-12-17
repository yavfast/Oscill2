package com.oscill.types;

import androidx.annotation.NonNull;

public class Unit {

    public static final String VOLT = "V";
    public static final String HERZ = "Hz";
    public static final String SECOND = "Sec";

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
    public String toString() {
        return dimension.getPrefix() + name;
    }
}

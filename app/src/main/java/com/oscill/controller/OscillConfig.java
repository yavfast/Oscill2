package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.types.Range;

import java.io.IOException;

public class OscillConfig {

    private final Oscill oscill;

    private final OscillProperty<Float> chanelSensitivity = new OscillProperty<Float>() {
        @NonNull
        @Override
        protected Range<Integer> requestNativePropertyRange() throws Exception {
            int min = getOscill().getChanelSensitivityMin();
            int max = getOscill().getChanelSensitivityMax();
            return new Range<>(min, max);
        }

        @Override
        protected Integer onNativeValueChanged(@NonNull Integer nativeValue) throws IOException {
            return getOscill().setChanelSensitivity(nativeValue);
        }

        @Override
        protected Integer realToNative(@NonNull Float realValue) {
            return Math.round(200f / realValue);
        }

        @Override
        protected Float nativeToReal(@NonNull Integer nativeValue) {
            return 200f / nativeValue;
        }
    };

    public OscillConfig(@NonNull Oscill oscill) {
        super();
        this.oscill = oscill;
    }

    @NonNull
    public Oscill getOscill() {
        return oscill;
    }

    @NonNull
    public OscillProperty<Float> getChanelSensitivity() {
        return chanelSensitivity;
    }
}

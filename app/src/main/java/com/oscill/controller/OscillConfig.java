package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

import java.io.IOException;

public class OscillConfig {

    private final Oscill oscill;

    private final OscillProperty<Float> chanelSensitivity = new OscillProperty<Float>() {
        @NonNull
        @Override
        protected Unit requestRealValueUnit() {
            return new Unit(Dimension.MILLI, Unit.VOLT);
        }

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

    private final OscillProperty<Integer> cpuTickLength = new OscillProperty<Integer>() {
        @NonNull
        @Override
        protected Unit requestRealValueUnit() {
            return new Unit(Dimension.PICO, Unit.SECOND);
        }

        @NonNull
        @Override
        protected Range<Integer> requestNativePropertyRange() throws Exception {
            int min = getOscill().getCPUTickMinLength();
            int max = 65500;
            return new Range<>(min, max);
        }

        @Override
        protected Integer requestNativeValue() throws Exception {
            return getOscill().getCPUTickDefLength();
        }

        @Override
        protected Integer onNativeValueChanged(@NonNull Integer nativeValue) throws Exception {
            return getOscill().setCPUTickLength(nativeValue);
        }

        @Override
        protected Integer realToNative(@NonNull Integer realValue) {
            return realValue / 10;
        }

        @Override
        protected Integer nativeToReal(@NonNull Integer nativeValue) {
            return nativeValue * 10;
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

    @NonNull
    public OscillProperty<Integer> getCpuTickLength() {
        return cpuTickLength;
    }
}

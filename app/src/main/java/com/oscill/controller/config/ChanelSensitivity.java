package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.Oscill;
import com.oscill.controller.OscillProperty;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

import java.io.IOException;

import static com.oscill.types.Dimension.MILLI;

public class ChanelSensitivity extends OscillProperty<Float> {

    private static final float DIV_COUNT = 8f;
    private static final float STEPS_BY_DIV = 32f;

    public ChanelSensitivity(@NonNull Oscill oscill) {
        super(oscill);
    }

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

    @NonNull
    @Override
    protected Integer requestNativeValue() throws Exception {
        return getOscill().getChanelSensitivity();
    }

    @Override
    protected Integer onNativeValueChanged(@NonNull Integer nativeValue) throws IOException {
        return getOscill().setChanelSensitivity(nativeValue);
    }

    @Override
    protected Integer realToNative(@NonNull Float realValue) {
        return Math.round(realValue);
    }

    @Override
    protected Float nativeToReal(@NonNull Integer nativeValue) {
        return (float)nativeValue;
    }

    public void setSensitivity(float value, @NonNull Dimension dimension) throws Exception {
        setRealValue(dimension.toDimension(value, Dimension.MILLI));
    }

    public float getSensitivityStep(@NonNull Dimension timeDim) {
        return MILLI.toDimension(getRealValue(), timeDim) / STEPS_BY_DIV;
    }

    @NonNull
    public Range<Float> getSensitivityRange(@NonNull Dimension timeDim) {
        float vMax = MILLI.toDimension(getRealValue(), timeDim) * DIV_COUNT / 2f;
        return new Range<>(-vMax, vMax);
    }


}

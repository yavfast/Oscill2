package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.Oscill;
import com.oscill.controller.OscillProperty;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

import java.io.IOException;

import static com.oscill.types.Dimension.MILLI;

public class ChannelSensitivity extends OscillProperty<Float> {

    private static final float DIV_COUNT = 8f;
    private static final float STEPS_BY_DIV = 32f;

    public ChannelSensitivity(@NonNull Oscill oscill) {
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
        int low = getOscill().getChanelSensitivityLow();
        int high = getOscill().getChanelSensitivityHigh();
        return new Range<>(high, low);
    }

    @NonNull
    @Override
    protected Integer requestNativeValue() throws Exception {
        return getOscill().getChanelSensitivity();
    }

    @Override
    protected Integer applyNativeValue(@NonNull Integer nativeValue) throws IOException {
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

    public void setSensitivity(@NonNull Sensitivity sensitivity) throws Exception {
        setSensitivity(sensitivity.getValue(), sensitivity.getDimension());
    }

    public void setSensitivity(float value, @NonNull Dimension dimension) throws Exception {
        setRealValue(dimension.toDimension(value, Dimension.MILLI));
    }

    @NonNull
    public Sensitivity getSensitivity() {
        float millisByDiv = getRealValue();
        for (Sensitivity sensitivity : Sensitivity.values()) {
            if (sensitivity.getValue(MILLI) == millisByDiv) {
                return sensitivity;
            }
        }
        return Sensitivity._10_V;
    }

    public float getSensitivityStep(@NonNull Dimension timeDim) {
        return MILLI.toDimension(getRealValue(), timeDim) / STEPS_BY_DIV;
    }

    @NonNull
    public Range<Float> getSensitivityRange(@NonNull Dimension timeDim) {
        float vMax = MILLI.toDimension(getRealValue(), timeDim) * DIV_COUNT / 2f;
        return new Range<>(-vMax, vMax);
    }

    public float getResolution() {
        return DIV_COUNT * STEPS_BY_DIV;
    }


}

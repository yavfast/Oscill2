package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.Oscill;
import com.oscill.controller.OscillProperty;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

import java.io.IOException;

public class ChanelSensitivity extends OscillProperty<Float> {

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

}

package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.Oscill;
import com.oscill.controller.OscillProperty;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

public class ChanelSyncLevel extends OscillProperty<Float> {

    private final ChanelSensitivity chanelSensitivity;

    public ChanelSyncLevel(@NonNull Oscill oscill, @NonNull ChanelSensitivity chanelSensitivity) {
        super(oscill);

        this.chanelSensitivity = chanelSensitivity;
        chanelSensitivity.addLinkedSetting(this);
    }

    @NonNull
    @Override
    protected Unit requestRealValueUnit() {
        return new Unit(Dimension.MILLI, Unit.VOLT);
    }

    @NonNull
    @Override
    protected Range<Integer> requestNativePropertyRange() throws Exception {
        return new Range<>(0, 255);
    }

    @NonNull
    @Override
    protected Integer requestNativeValue() throws Exception {
        return getOscill().getChanelSyncLevel();
    }

    @Override
    protected Integer applyNativeValue(@NonNull Integer nativeValue) throws Exception {
        return getOscill().setChanelSyncLevel(nativeValue);
    }

    @Override
    protected Integer realToNative(@NonNull Float realValue) {
        Range<Float> sensitivityRange = chanelSensitivity.getSensitivityRange(Dimension.MILLI);
        float resolution = chanelSensitivity.getResolution();
        return Math.round(realValue / (sensitivityRange.getUpper() / resolution));
    }

    @Override
    protected Float nativeToReal(@NonNull Integer nativeValue) {
        Range<Float> sensitivityRange = chanelSensitivity.getSensitivityRange(Dimension.MILLI);
        float resolution = chanelSensitivity.getResolution();
        return (sensitivityRange.getUpper() / resolution) * nativeValue;
    }
}

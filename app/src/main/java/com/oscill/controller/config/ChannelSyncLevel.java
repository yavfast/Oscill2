package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.Oscill;
import com.oscill.controller.OscillProperty;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

public class ChannelSyncLevel extends OscillProperty<Float> {

    private final ChannelSensitivity channelSensitivity;

    public ChannelSyncLevel(@NonNull Oscill oscill, @NonNull ChannelSensitivity channelSensitivity) {
        super(oscill);

        this.channelSensitivity = channelSensitivity;
        channelSensitivity.addLinkedSetting(this);
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
        Range<Float> sensitivityRange = channelSensitivity.getSensitivityRange(Dimension.MILLI);
        float resolution = channelSensitivity.getResolution();
        float vMin = sensitivityRange.getLower();
        float vMax = sensitivityRange.getUpper();
        return Math.round(realValue / ((vMax - vMin) / resolution));
    }

    @Override
    protected Float nativeToReal(@NonNull Integer nativeValue) {
        Range<Float> sensitivityRange = channelSensitivity.getSensitivityRange(Dimension.MILLI);
        float resolution = channelSensitivity.getResolution();
        float vMin = sensitivityRange.getLower();
        float vMax = sensitivityRange.getUpper();
        return vMin + (((vMax - vMin) / resolution) * nativeValue);
    }
}

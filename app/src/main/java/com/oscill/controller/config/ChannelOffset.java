package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.Oscill;
import com.oscill.controller.OscillProperty;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

public class ChannelOffset extends OscillProperty<Float> {

    private final ChannelSensitivity channelSensitivity;

    public ChannelOffset(@NonNull Oscill oscill, @NonNull ChannelSensitivity channelSensitivity) {
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
    protected Integer requestNativeValue() throws Exception {
        return getOscill().getChanelOffset();
    }

    @NonNull
    @Override
    protected Range<Integer> requestNativePropertyRange() throws Exception {
        int min = getOscill().getChanelOffsetMin();
        int max = getOscill().getChanelOffsetMax();
        return new Range<>(min, max);
    }

    @Override
    protected Integer applyNativeValue(@NonNull Integer nativeValue) throws Exception {
        return getOscill().setChanelOffset(nativeValue);
    }

    @Override
    protected Integer realToNative(@NonNull Float realValue) {
        return Math.round(realValue / (channelSensitivity.getRealValue() * 8f / 256f));
    }

    @Override
    protected Float nativeToReal(@NonNull Integer nativeValue) {
        return (channelSensitivity.getRealValue() * 8f / 256f) * nativeValue;
    }

    public void setOffset(float value, @NonNull Dimension dimension) throws Exception {
        setRealValue(dimension.toDimension(value, Dimension.MILLI).floatValue());
    }
}

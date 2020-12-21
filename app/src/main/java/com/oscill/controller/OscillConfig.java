package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.controller.config.ChanelOffset;
import com.oscill.controller.config.ChanelSensitivity;
import com.oscill.controller.config.CpuTickLength;
import com.oscill.controller.config.RealtimeSamplingPeriod;
import com.oscill.controller.config.SamplesCount;
import com.oscill.types.Dimension;
import com.oscill.utils.executor.OnResult;

import java.io.IOException;

public class OscillConfig {

    private final Oscill oscill;

    private final ChanelSensitivity chanelSensitivity;
    private final ChanelOffset chanelOffset;

    private final CpuTickLength cpuTickLength;
    private final RealtimeSamplingPeriod realtimeSamplingPeriod;
    private final SamplesCount samplesCount;

    public OscillConfig(@NonNull Oscill oscill) {
        super();
        this.oscill = oscill;
        this.chanelSensitivity = new ChanelSensitivity(oscill);
        this.chanelOffset = new ChanelOffset(oscill, chanelSensitivity);
        this.cpuTickLength = new CpuTickLength(oscill);
        this.samplesCount = new SamplesCount(oscill);
        this.realtimeSamplingPeriod = new RealtimeSamplingPeriod(oscill, cpuTickLength, samplesCount);
    }

    @NonNull
    public Oscill getOscill() {
        return oscill;
    }

    @NonNull
    public ChanelSensitivity getChanelSensitivity() {
        return chanelSensitivity;
    }

    @NonNull
    public ChanelOffset getChanelOffset() {
        return chanelOffset;
    }

    @NonNull
    public CpuTickLength getCpuTickLength() {
        return cpuTickLength;
    }

    @NonNull
    public RealtimeSamplingPeriod getRealtimeSamplingPeriod() {
        return realtimeSamplingPeriod;
    }

    @NonNull
    public SamplesCount getSamplesCount() {
        return samplesCount;
    }

    public void requestData(@NonNull OnResult<OscillData> onResult) {
        try {
            int responseTimeout = (int)realtimeSamplingPeriod.getDivTime(Dimension.MILLI);
            byte[] data = oscill.getData(responseTimeout);
            if (data.length > 4) {
                OscillData oscillData = new OscillData(this, data);
                onResult.of(oscillData);
            } else {
                onResult.empty();
            }
        } catch (IOException e) {
            onResult.error(e);
        }
    }
}

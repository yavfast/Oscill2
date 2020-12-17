package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.controller.config.ChanelSensitivity;
import com.oscill.controller.config.CpuTickLength;
import com.oscill.controller.config.RealtimeSamplingPeriod;

public class OscillConfig {

    private final Oscill oscill;

    private final ChanelSensitivity chanelSensitivity;
    private final CpuTickLength cpuTickLength;
    private final RealtimeSamplingPeriod realtimeSamplingPeriod;

    public OscillConfig(@NonNull Oscill oscill) {
        super();
        this.oscill = oscill;
        this.chanelSensitivity = new ChanelSensitivity(oscill);
        this.cpuTickLength = new CpuTickLength(oscill);
        this.realtimeSamplingPeriod = new RealtimeSamplingPeriod(oscill, cpuTickLength);
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
    public CpuTickLength getCpuTickLength() {
        return cpuTickLength;
    }

    @NonNull
    public RealtimeSamplingPeriod getRealtimeSamplingPeriod() {
        return realtimeSamplingPeriod;
    }
}

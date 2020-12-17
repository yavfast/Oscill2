package com.oscill.controller;

import androidx.annotation.NonNull;

public class OscillData {

    public final OscillConfig config;
    public final byte[] data;

    public OscillData(@NonNull OscillConfig config, @NonNull byte[] data) {
        this.config = config;
        this.data = data;
    }
}

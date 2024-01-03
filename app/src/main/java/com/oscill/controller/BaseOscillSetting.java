package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.utils.Log;

import java.util.ArrayList;

public abstract class BaseOscillSetting {

    protected final String TAG = Log.getTag(this.getClass());

    private final Oscill oscill;
    private final ArrayList<BaseOscillSetting> linkedSettings = new ArrayList<>();

    protected BaseOscillSetting(@NonNull Oscill oscill) {
        super();
        this.oscill = oscill;
    }

    @NonNull
    public Oscill getOscill() {
        return oscill;
    }

    public void addLinkedSetting(@NonNull BaseOscillSetting setting) {
        linkedSettings.add(setting);
    }

    public void reset() {
        onReset();
        resetLinkedSettings();
    }

    public void resetLinkedSettings() {
        for (BaseOscillSetting linkedSetting : linkedSettings) {
            linkedSetting.reset();
        }
    }

    protected abstract void onReset();

    public void release() {
        try {
            oscill.disconnect();
        } catch (Throwable e) {
            Log.e(TAG, e);
        }
    }
}

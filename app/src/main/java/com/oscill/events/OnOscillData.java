package com.oscill.events;

import androidx.annotation.NonNull;

import com.oscill.controller.OscillData;
import com.oscill.utils.executor.IBroadcastEvent;

public class OnOscillData implements IBroadcastEvent {

    public final OscillData oscillData;

    public OnOscillData(@NonNull OscillData oscillData) {
        this.oscillData = oscillData;
    }
}

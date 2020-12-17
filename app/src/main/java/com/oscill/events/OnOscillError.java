package com.oscill.events;

import androidx.annotation.NonNull;

import com.oscill.utils.executor.IBroadcastEvent;

public class OnOscillError implements IBroadcastEvent {

    private final Throwable throwable;

    public OnOscillError(@NonNull Throwable throwable) {
        this.throwable = throwable;
    }

    @NonNull
    public Throwable getError() {
        return throwable;
    }
}

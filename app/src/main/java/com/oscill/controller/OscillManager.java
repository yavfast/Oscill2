package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.events.OnOscillConnected;
import com.oscill.events.OnOscillData;
import com.oscill.events.OnOscillError;
import com.oscill.types.SuspendValue;
import com.oscill.utils.executor.EventsController;
import com.oscill.utils.executor.Executor;
import com.oscill.utils.executor.ObjRunnable;

import java.util.concurrent.atomic.AtomicBoolean;

public class OscillManager {

    private static final SuspendValue<OscillConfig> oscillConfig = new SuspendValue<>(() -> {
        throw new IllegalStateException("Use init");
    });

    private static final AtomicBoolean isActive = new AtomicBoolean(false);

    @NonNull
    public static OscillConfig getOscillConfig() {
        return oscillConfig.get();
    }

    public static boolean isConnected() {
        return oscillConfig.hasValue();
    }

    public static boolean isActive() {
        return isActive.get();
    }

    public static void init() {
        Executor.runInSyncQueue(() -> {
            if (!isConnected()) {
                OscillUsbManager.checkDevice(onCheckDeviceResult ->
                        onCheckDeviceResult.doIfPresent(usbDevice -> {
                            OscillUsbManager.connectToDevice(onConnectResult ->
                                    onConnectResult.doIfPresent(oscill -> {
                                        oscillConfig.set(new OscillConfig(oscill));
                                        EventsController.sendEvent(new OnOscillConnected());
                                    }).doIfError(e -> EventsController.sendEvent(new OnOscillError(e)))
                            );
                        }).doIfError(e -> EventsController.sendEvent(new OnOscillError(e)))
                );
            }
        });
    }

    public static void runConfigTask(@NonNull ObjRunnable<OscillConfig> task) {
        Executor.runInSyncQueue(() -> {
            if (isConnected()) {
                task.run(getOscillConfig());
            }
        });
    }

    public static void requestNextData() {
        Executor.runInSyncQueue(() -> {
            if (isConnected()) {
                getOscillConfig().requestData(onResult ->
                        onResult.doIfPresent(oscillData -> {
                            if (isActive()) {
                                requestNextData();
                                EventsController.sendEvent(new OnOscillData(oscillData));
                            }
                        }).doIfError(e -> EventsController.sendEvent(new OnOscillError(e)))
                );
            }
        });
    }

    public static void pause() {
        isActive.set(false);
    }
}

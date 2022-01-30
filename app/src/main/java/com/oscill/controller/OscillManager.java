package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.events.OnOscillConfigChanged;
import com.oscill.events.OnOscillConnected;
import com.oscill.events.OnOscillData;
import com.oscill.events.OnOscillError;
import com.oscill.types.SuspendValue;
import com.oscill.utils.executor.EventsController;
import com.oscill.utils.executor.Executor;
import com.oscill.utils.executor.UnsafeObjRunnable;

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

    public static void runConfigTask(@NonNull UnsafeObjRunnable<OscillConfig> task) {
        Executor.runInSyncQueue(() -> {
            if (isConnected()) {
                try {
                    task.run(getOscillConfig());
                    EventsController.sendEvent(new OnOscillConfigChanged());
                } catch (Throwable e) {
                    EventsController.sendEvent(new OnOscillError(e));
                }
            }
        });
    }

    public static void requestNextData() {
        Executor.runInSyncQueue(() -> {
            if (isConnected()) {
                getOscillConfig().requestData(onResult ->
                        onResult.doIfPresent(OscillManager::prepareData)
                                .doIfError(e -> EventsController.sendEvent(new OnOscillError(e)))
                );
            }
        });
    }

    public static void pause() {
        isActive.set(false);
    }

    public static void start() {
        if (isActive.compareAndSet(false, true)) {
            doStart();
        }
    }

    private static void doStart() {
        Executor.runInSyncQueue(() -> {
            if (isConnected()) {
                getOscillConfig().requestData(onResult ->
                        onResult.doIfPresent(oscillData -> {
                            if (isActive()) {
                                doStart();
                                prepareData(oscillData);
                            }
                        }).doIfEmpty(() -> {
                            if (isActive()) {
                                doStart();
                            }
                        }).doIfError(e -> EventsController.sendEvent(new OnOscillError(e)))
                );
            }
        });
    }

    private static void prepareData(@NonNull OscillData oscillData) {
        Executor.runInSyncQueue2(() -> {
            oscillData.prepareData();
            EventsController.sendEvent(new OnOscillData(oscillData));
        });
    }
}

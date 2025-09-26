package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.controller.config.ProcessingTypeMode;
import com.oscill.controller.settings.OscillSettings;
import com.oscill.events.OnOscillConfigChanged;
import com.oscill.events.OnOscillConnected;
import com.oscill.events.OnOscillData;
import com.oscill.events.OnOscillError;
import com.oscill.types.SuspendValue;
import com.oscill.utils.ConvertUtils;
import com.oscill.utils.executor.EventsController;
import com.oscill.utils.executor.Executor;
import com.oscill.utils.executor.OnResult;
import com.oscill.utils.executor.UnsafeObjRunnable;

import java.io.IOException;
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

    public static void reset() {
        pause();

        Executor.runInSyncQueue(() -> {
            oscillConfig.reset(OscillConfig::release);
            init();
        });
    }

    public static void loadLastSettings() {
        Executor.runInSyncQueue(() -> {
            OscillSettings settings = OscillPrefs.loadLastSettings();
            if (settings != null) {
                applySettings(settings);
            }
        });
    }

    public static void applySettings(@NonNull OscillSettings settings) {
        runConfigTask(oscillConfig -> {
            oscillConfig.getCpuTickLength().setRealValueStr(settings.cpuTickLength);

            Executor.doIfExists(settings.processingTypeMode, processingTypeMode -> {
                Executor.doSafe(() -> {
                    ProcessingTypeMode.ProcessingType processingType = ConvertUtils.getEnumByName(processingTypeMode.processingType,
                            ProcessingTypeMode.ProcessingType.class, ProcessingTypeMode.ProcessingType.REALTIME);
                    oscillConfig.getProcessingTypeMode().setProcessingType(processingType);
                });

                Executor.doSafe(() -> {
                    ProcessingTypeMode.DataOutputType dataOutputType = ConvertUtils.getEnumByName(processingTypeMode.dataOutputType,
                            ProcessingTypeMode.DataOutputType.class, ProcessingTypeMode.DataOutputType.POST_PROCESSING);
                    oscillConfig.getProcessingTypeMode().setDataOutputType(dataOutputType);
                });

                Executor.doSafe(() -> {
                    ProcessingTypeMode.BufferType bufferType = ConvertUtils.getEnumByName(processingTypeMode.bufferType,
                            ProcessingTypeMode.BufferType.class, ProcessingTypeMode.BufferType.SYNC);
                    oscillConfig.getProcessingTypeMode().setBufferType(bufferType);
                });
            });


        });
    }

    public static void saveSettings() {
        runConfigTask(oscillConfig -> {

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

    public static void requestNextData(@NonNull OnResult<OscillData> onResult) {
        Executor.runInSyncQueue(() -> {
            if (isConnected()) {
                getOscillConfig().requestData(onResult);
            } else {
                onResult.error(new IOException("No connection"));
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

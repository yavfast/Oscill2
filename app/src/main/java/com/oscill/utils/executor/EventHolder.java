package com.oscill.utils.executor;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.ClassUtils;
import com.oscill.utils.Log;
import com.oscill.utils.ObjectUtils;

import java.lang.ref.WeakReference;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

public class EventHolder<E extends IBroadcastEvent> {

    private static final String TAG = Log.getTag(EventHolder.class, Log.Level.WARN);

    private final WeakReference<Object> holderRef;
    private final Class<? extends IBroadcastEvent> clazz;
    private ObjRunnable<E> onReceive;
    private ObjCallable<E, Boolean> onAcceptEvent;
    private final boolean runInBackground;
    private final AtomicBoolean isActive = new AtomicBoolean(false);
    private boolean isReceiveOnce = false;
    private final AtomicInteger receiveCounter = new AtomicInteger(0);

    EventHolder(@Nullable Object holder, @NonNull Class<? extends IBroadcastEvent> clazz, @NonNull ObjRunnable<E> onReceive, boolean runInBackground) {
        this.holderRef = new WeakReference<>(holder);
        this.clazz = clazz;
        this.onReceive = onReceive;
        this.runInBackground = runInBackground;
    }

    @NonNull
    public EventHolder<E> setOnAcceptEvent(@NonNull ObjCallable<E, Boolean> onAcceptEvent) {
        this.onAcceptEvent = onAcceptEvent;
        return this;
    }

    @NonNull
    public EventHolder<E> receiveOnce() {
        this.isReceiveOnce = true;
        return this;
    }

    private boolean isActive() {
        return isActive.get();
    }

    @Nullable
    public Object getHolder() {
        return holderRef.get();
    }

    @NonNull
    public Class<? extends IBroadcastEvent> getEventClass() {
        return clazz;
    }

    @SuppressWarnings("unchecked")
    private boolean isAccept(@NonNull IBroadcastEvent event) {
        return Executor.getIfExists(onAcceptEvent, obj -> obj.call((E)event), true);
    }

    private boolean isAllowReceive() {
        return receiveCounter.incrementAndGet() == 1 || !isReceiveOnce;
    }

    void execute(@NonNull IBroadcastEvent event) {
        if (isActive() && isAccept(event) && isAllowReceive()) {
            if (runInBackground) {
                Executor.runInBackgroundAsync(() -> run(event));
            } else {
                Executor.runInUIThreadAsync(() -> run(event));
            }
        } else {
            Log.d(TAG, "Skip: ", this);
        }
    }

    @SuppressWarnings("unchecked")
    private void run(@NonNull IBroadcastEvent event) {
        if (isActive() && isAccept(event)) {
            Log.i(TAG, "OnReceive event: ", event, "; holder: ", holderRef.get());
            Executor.doIfExists(onReceive, runnable -> runnable.run((E) event));
            onAfterReceive();
        }
    }

    private void onAfterReceive() {
        if (isReceiveOnce) {
            pause();
            EventsController.unregister(this);
        }
    }

    @NonNull
    public EventHolder<E> pause() {
        if (isActive.compareAndSet(true, false)) {
            Log.i(TAG, "Pause: ", this);
        }
        return this;
    }

    @NonNull
    public EventHolder<E> resume() {
        if (isActive.compareAndSet(false, true)) {
            Log.i(TAG, "Resume: ", this);
        }
        return this;
    }

    void release() {
        pause();
        Log.i(TAG, "Release: ", this);
        onReceive = null;
        onAcceptEvent = null;
    }

    @NonNull
    @Override
    public String toString() {
        return "EventHolder{" +
                "holder=" + holderRef.get() +
                ", eventClass=" + ClassUtils.getClassTag(clazz) +
                ", async=" + runInBackground +
                ", isActive=" + isActive +
                '}';
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        EventHolder<?> that = (EventHolder<?>) o;
        return ObjectUtils.equals(holderRef.get(), that.holderRef.get()) &&
                ObjectUtils.equals(clazz, that.clazz) &&
                ObjectUtils.equals(onReceive, that.onReceive);
    }

    @Override
    public int hashCode() {
        return (int) ObjectUtils.getHashCode(holderRef.get(), clazz, onReceive);
    }
}

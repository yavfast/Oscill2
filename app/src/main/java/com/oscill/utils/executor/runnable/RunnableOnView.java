package com.oscill.utils.executor.runnable;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.Log;
import com.oscill.utils.ViewUtils;

import java.lang.ref.WeakReference;

public abstract class RunnableOnView<T> implements MainThreadRunnable {

    private final static String TAG = Log.getTag(RunnableOnView.class);

    private final WeakReference<T> viewRef;

    public RunnableOnView(@NonNull T view) {
        viewRef = new WeakReference<>(view);
    }

    @Nullable
    public T getView() {
        return viewRef.get();
    }

    @Override
    public void run() {
        T view = getView();
        if (ViewUtils.checkUIComponent(view)) {
            run(view);
        } else {
            Log.w(TAG, "Skip run task on view: ", view != null ? Log.getTag(view.getClass()) : "null");
        }
    }

    abstract public void run(@NonNull T view);
}

package com.oscill.utils.executor;

import java.util.concurrent.Callable;

public interface UnsafeCallable<T> extends Callable<T> {

    T unsafeCall() throws Exception;

    default T call() throws Exception {
        try {
            return unsafeCall();
        } catch (Exception e) {
            throw e;
        } catch (Throwable throwable) {
            throw new IllegalStateException(throwable);
        }
    }

}

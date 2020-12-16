package com.oscill.utils.executor;

public interface ValueCallable<V> {
    V call() throws Exception;
}

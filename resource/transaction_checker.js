var TransactionChecker = function(txn_id, retries, timeout) {
    this.txn_id = txn_id;
    if (typeof retries != "undefined") {
        this.retries = retries;
    } else {
        this.retries = 5;
    }
    if (typeof timeout != "undefined") {
        this.timeout = timeout;
    } else {
        this.timeout = 2000;
    }
};
TransactionChecker.prototype.query = function (success_callback, error_callback) {
    // success_callback = function(type, state, last_mod, options) {};
    // error_callback = function(reason, description) {};

    var _this = this;

    $.ajax({
        method: "GET",
        url: sprintf("/transaction/view/%s", _this.txn_id),
        contentType: "application/json",
        success: function (data, textStatus, jqXHR) {
            if (jqXHR.status == 200 && jqXHR.statusText == "OK" && jqXHR.getResponseHeader("Content-Type") == "application/json") {
                success_callback(data["type"], data["state"], data["last_mod"], data["options"]);
            } else {
                error_callback("Unexpected response", sprintf("%s %s", jqXHR.status, jqXHR.statusText));
            }
        },
        error: function (jqXHR, textStatus, errorThrown) {
            error_callback(textStatus, errorThrown);
        },
        timeout: _this.timeout
    });
};
TransactionChecker.prototype.run = function (completed_callback, cancelled_callback, error_callback, progress_callback) {
    // completed_callback = function(last_mod, options) {};
    // cancelled_callback = function(last_mod, options, reason_to_cancel) {};
    // error_callback = function(reason, description) {};
    // progress_callback = function() {};

    var _this = this;

    var checker = function() {
        _this.query(
            function (type, state, last_mod, options) {
                if (state == "completed") {
                    completed_callback(last_mod, options);
                } else if (state == "cancelled") {
                    cancelled_callback(last_mod, options, "");
                } else {
                    _this.retries = _this.retries - 1;
                    if (_this.retries > 0) {
                        setTimeout(checker, _this.timeout);
                    } else {
                        error_callback("Retry count exceeded", "Transaction did not complete within checked period of time");
                    }
                }
            },
            function (reason, description) {
                error_callback(reason, description);
            }
        );
        // Report progress
        if (typeof progress_callback != "undefined") {
            progress_callback();
        }
    };
    checker();
};

var TransactionCheckerUI = function(txn_id, retries, timeout) {
    this.txn_id = txn_id;
    this.retries = retries;
    this.timeout = timeout;
};
TransactionCheckerUI.prototype.run = function (completed_callback, cancelled_callback, other_callback) {
    // completed_callback = function(last_mod, options) {};
    // cancelled_callback = function(last_mod, options, reason_to_cancel) {};
    // other_callback = function() {};

    var txn_checker = new TransactionChecker(this.txn_id, this.retries, this.timeout);
    txn_checker.run(
        // completed callback
        function (last_mod, options) {
            // Notification
            var notification = $.notify.create(
                "Transaction has been completed", {
                    type: "success", adjustScroll: true,
                    afterHide: function (event, notify) {
                        $(this).remove();
                    }
                }
            );
            window.setTimeout(function () {
                notification.notify("hide");
            }, 3000);

            completed_callback(last_mod, options);
        },
        // cancelled callback
        function (last_mod, options, reason) {
            // Notification
            var notification = $.notify.create(
                "Transaction has been cancelled", {
                    type: "warning", adjustScroll: true,
                    afterHide: function (event, notify) {
                        $(this).remove();
                    }
                }
            );

            cancelled_callback(last_mod, options, reason);
        },
        // error callback
        function (reason, description) {
            // Notification
            var notification = $.notify.create(
                sprintf("Transaction has NOT been completed | %s | %s", reason, description),
                {
                    type: "error", adjustScroll: true,
                    afterHide: function (event, notify) {
                        $(this).remove();
                    }
                }
            );

            other_callback();
        },
        // progress callback
        function () {
            var notification = $.notify.create(
                "Verifying transaction status", {
                    type: "success", adjustScroll: true,
                    afterHide: function (event, notify) {
                        $(this).remove();
                    }
                }
            );
            window.setTimeout(function () {
                notification.notify("hide");
            }, 3000);
        }
    );
};

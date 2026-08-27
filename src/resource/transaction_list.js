var transaction_view = function(id_txn) {
    console.log(sprintf("View transaction: %s", id_txn));

    var notify_progress = function() {
        var notification = $.notify.create(
            "Transaction view: requesting ...", {
                type: "success", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
        window.setTimeout(function () {
            notification.notify("hide");
        }, 3000);
    };

    var notify_error = function(reason, description) {
        var notification = $.notify.create(
            sprintf("Transaction view: NOT rendered | %s | %s", reason, description),
            {
                type: "error", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
    };

    var render_view = function(type, state, last_mod, options) {
        console.log(sprintf("View transaction: %s %s %s %s", type, state, last_mod, options));

        thedialog = $("div#transaction_view").clone().removeAttr("id");
        thedialog.find("table tr:nth-child(1) td").text(sprintf("%s/%s", id_txn, type));
        thedialog.find("table tr:nth-child(2) td").text(state);
        thedialog.find("table tr:nth-child(3) td").text(last_mod);
        thedialog.find("code").text(options);
        $("body").append(thedialog);
        thedialog.dialog({autoOpen: false, modal: false, width: "auto", height: "auto",
            buttons: [
                {text: "Close", click: function () {
                    $(this).dialog("close");
                }},
            ],
            close: function () {
                $(this).dialog("destroy").remove();
            }
        });
        thedialog.find("form").on("submit", function (event) {
            event.preventDefault();
        });
        thedialog.dialog("open");
    };


    notify_progress();
    $.ajax({
        method: "GET",
        url: sprintf("/transaction/view/%s", id_txn),
        contentType: "application/json",
        success: function (data, textStatus, jqXHR) {
            if (jqXHR.status == 200 && jqXHR.statusText == "OK" && jqXHR.getResponseHeader("Content-Type") == "application/json") {
                render_view(data["type"], data["state"], data["last_mod"], JSON.stringify(data["options"]));
            } else {
                notify_error(jqXHR.status, jqXHR.statusText);
            }
        },
        error: function (jqXHR, textStatus, errorThrown) {
            notify_error(textStatus, errorThrown);
        },
        timeout: 3000
    });
};

var transaction_commit = function(id_txn) {
    console.log(sprintf("Commit transaction: %s", id_txn));

    var notify_progress = function() {
        var notification = $.notify.create(
            "Transaction commit: posting ...", {
                type: "success", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
        window.setTimeout(function () {
            notification.notify("hide");
        }, 3000);
    };

    var notify_success = function() {
        var notification = $.notify.create(
            "Transaction commit: posted", {
                type: "success", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
        window.setTimeout(function () {
            notification.notify("hide");
        }, 3000);
    };

    var notify_error = function(reason, description) {
        var notification = $.notify.create(
            sprintf("Transaction commit: NOT posted | %s | %s", reason, description),
            {
                type: "error", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
    };

    notify_progress();
    $.ajax({
        method: "POST",
        url: sprintf("/transaction/commit/%s", id_txn),
        success: function (data, textStatus, jqXHR) {
            if (jqXHR.status == 200 && jqXHR.statusText == "OK" && jqXHR.getResponseHeader("Content-Type") == "application/json") {
                notify_success();
                // success_callback(data["type"], data["state"], data["last_mod"]);
            } else {
                notify_error(jqXHR.status, jqXHR.statusText);
            }
        },
        error: function (jqXHR, textStatus, errorThrown) {
            notify_error(textStatus, errorThrown);
        },
        timeout: 3000
    });
};

var transaction_cancel = function(id_txn) {
    console.log(sprintf("Cancel transaction: %s", id_txn));

    var notify_progress = function() {
        var notification = $.notify.create(
            "Transaction cancel: posting ...", {
                type: "success", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
        window.setTimeout(function () {
            notification.notify("hide");
        }, 3000);
    };

    var notify_success = function() {
        var notification = $.notify.create(
            "Transaction cancel request: posted", {
                type: "success", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
        window.setTimeout(function () {
            notification.notify("hide");
        }, 3000);
    };

    var notify_error = function(reason, description) {
        var notification = $.notify.create(
            sprintf("Transaction cancel: NOT posted | %s | %s", reason, description),
            {
                type: "error", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
    };

    notify_progress();
    $.ajax({
        method: "POST",
        url: sprintf("/transaction/cancel/%s", id_txn),
        success: function (data, textStatus, jqXHR) {
            if (jqXHR.status == 200 && jqXHR.statusText == "OK" && jqXHR.getResponseHeader("Content-Type") == "application/json") {
                notify_success();
                // success_callback(data["type"], data["state"], data["last_mod"]);
            } else {
                notify_error(jqXHR.status, jqXHR.statusText);
            }
        },
        error: function (jqXHR, textStatus, errorThrown) {
            notify_error(textStatus, errorThrown);
        },
        timeout: 3000
    });
};

var transaction_recover = function(id_txn) {
    console.log(sprintf("Recover transaction: %s", id_txn));

    var notify_progress = function() {
        var notification = $.notify.create(
            "Transaction recover: posting ...", {
                type: "success", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
        window.setTimeout(function () {
            notification.notify("hide");
        }, 3000);
    };

    var notify_success = function() {
        var notification = $.notify.create(
            "Transaction recover: posted", {
                type: "success", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
        window.setTimeout(function () {
            notification.notify("hide");
        }, 3000);
    };

    var notify_error = function(reason, description) {
        var notification = $.notify.create(
            sprintf("Transaction recover: NOT posted | %s | %s", reason, description),
            {
                type: "error", adjustScroll: true,
                afterHide: function (event, notify) {
                    $(this).remove();
                }
            }
        );
    };

    notify_progress();
    $.ajax({
        method: "POST",
        url: sprintf("/transaction/recover/%s", id_txn),
        success: function (data, textStatus, jqXHR) {
            if (jqXHR.status == 200 && jqXHR.statusText == "OK" && jqXHR.getResponseHeader("Content-Type") == "application/json") {
                notify_success();
                // success_callback(data["type"], data["state"], data["last_mod"]);
            } else {
                notify_error(jqXHR.status, jqXHR.statusText);
            }
        },
        error: function (jqXHR, textStatus, errorThrown) {
            notify_error(textStatus, errorThrown);
        },
        timeout: 3000
    });
};

// Agent create
var agent_create_dialog = function(confirm_callback /* (name, address) */) {
    var confirm = function () {
        var name = thedialog.find("form input[type=text][name=name]").val();
        var address = new Object();
        var address_street = thedialog.find("form input[type=text][name=address_street]").val();
        if (!!address_street) { address["street"] = address_street; }
        var address_city = thedialog.find("form input[type=text][name=address_city]").val();
        if (!!address_city) { address["city"] = address_city; }
        var address_postal_code = thedialog.find("form input[type=text][name=address_postal_code]").val();
        if (!!address_postal_code) { address["postal_code"] = address_postal_code; }
        var address_country = thedialog.find("form select[name=address_country] option:selected").val();
        if (!!address_country) { address["country"] = address_country; }
        confirm_callback(name, address);
        thedialog.dialog("close");
    };

    var thedialog = $("div#agent_create");
    thedialog.dialog({autoOpen: false, modal: true, width: "auto", height: "auto",
        buttons: [
            {text: "Add an agent", click: confirm},
            {text: "Cancel", click: function () {
                thedialog.dialog("close");
            }},
        ],
        close: function () {
            thedialog.find("form").trigger("reset");
            thedialog.find("form").off("submit");
        }
    });
    thedialog.find("form").on("submit", function (event) {
        event.preventDefault();
        confirm();
    });
    thedialog.dialog("open");
};
var agent_create = function(name, address, success_callback /* (id_agent) */, failure_callback /* () */) {
    $.ajax({method: "POST", url: "/agent/edit",
        contentType: "application/json",
        data: JSON.stringify({op: "create", args: {name: name, address: address}}),
        dataType: "json",
        success: function (data, textStatus, jqXHR) {
            success_callback(data.id);
        },
        error: function (jqXHR, textStatus, errorThrown) {
            failure_callback();
        },
        timeout: 3000
    });
};

// Agent close
var agent_close = function(id_agent, success_callback /* () */, failure_callback /* () */) {
    $.ajax({method: "POST", url: "/agent/edit",
        contentType: "application/json",
        data: JSON.stringify({op: "close", args: {id: id_agent}}),
        dataType: "json",
        success: function (data, textStatus, jqXHR) {
            if (data["closed"] == true) {
                success_callback();
            } else {
                failure_callback();
            }
        },
        error: function (jqXHR, textStatus, errorThrown) {
            failure_callback();
        },
        timeout: 3000
    });
};

// Agent update
var agent_update_dialog = function(name, address, confirm_callback /* (name, address) */) {
    var thedialog = $("div#agent_update");
    thedialog.find("form input[type=text][name=name]").val(name);
    var address_street = address["street"];
    if (!!address_street) { thedialog.find("form input[type=text][name=address_street]").val(address_street); }
    var address_city = address["city"];
    if (!!address_city) { thedialog.find("form input[type=text][name=address_city]").val(address_city); }
    var address_postal_code = address["postal_code"];
    if (!!address_postal_code) { thedialog.find("form input[type=text][name=address_postal_code]").val(address_postal_code); }
    var address_country = address["country"];
    if (!!address_country) { thedialog.find("form select[name=address_country]").val(address_country); }

    var confirm = function () {
        var name = thedialog.find("form input[type=text][name=name]").val();
        var address = new Object();
        var address_street = thedialog.find("form input[type=text][name=address_street]").val();
        if (!!address_street) { address["street"] = address_street; }
        var address_city = thedialog.find("form input[type=text][name=address_city]").val();
        if (!!address_city) { address["city"] = address_city; }
        var address_postal_code = thedialog.find("form input[type=text][name=address_postal_code]").val();
        if (!!address_postal_code) { address["postal_code"] = address_postal_code; }
        var address_country = thedialog.find("form select[name=address_country] option:selected").val();
        if (!!address_country) { address["country"] = address_country; }
        confirm_callback(name, address);
        thedialog.dialog("close");
    };

    thedialog.dialog({autoOpen: false, height: "auto", width: "auto", modal: true,
        buttons: [
            {text: "Update the agent", click: confirm},
            {text: "Cancel", click: function () {
                thedialog.dialog("close");
            }},
        ],
        close: function () {
            thedialog.find("form").trigger("reset");
            thedialog.find("form").off("submit");
        }
    });
    thedialog.find("form").on("submit", function (event) {
        event.preventDefault();
        confirm();
    });
    thedialog.dialog("open");
};
var agent_update = function(id_agent, name, address, success_callback, failure_callback) {
    $.ajax({method: "POST", url: "/agent/edit",
        contentType: "application/json",
        data: JSON.stringify({op: "update", args: {id: id_agent, name: name, address: address}}),
        dataType: "json",
        success: function (data, textStatus, jqXHR) {
            if (data["updated"] == true) {
                success_callback();
            } else {
                failure_callback();
            }
        },
        error: function (jqXHR, textStatus, errorThrown) {
            failure_callback();
        },
        timeout: 3000
    });
};

function WSSHClient(term) {
    this.term = term;
};

WSSHClient.prototype._generateEndpoint = function(options) {
    if (window.location.protocol == 'https:') {
        var protocol = 'wss://';
    }
    else {
        var protocol = 'ws://';
    }
    var endpoint = protocol + window.location.host;
    if( options.bridge_id ) {
        endpoint +='/websocket?id=' + options.bridge_id;
    }
    else {        
        endpoint += '/ssh/connect';
        endpoint += '?username=' + encodeURIComponent(options.username);
        endpoint += '&hostname=' + encodeURIComponent(options.hostname);
        if (options.authentication_method == 'password') {
            endpoint += '&password=' + encodeURIComponent(options.password);
        }
        else if (options.authentication_method == 'private_key') {
            endpoint += '&private_key=' + encodeURIComponent(options.private_key);
            if (options.key_passphrase !== undefined)
                endpoint += '&key_passphrase=' + encodeURIComponent(
                    options.key_passphrase);
        }
        else {
            return null;
        }
        endpoint += '&port=' + encodeURIComponent(options.port);
        if (options.command != "") {
            endpoint += '&run=' + encodeURIComponent(
                options.command);
        }
    }
    return endpoint;
};

WSSHClient.prototype.connect = function(options) {
    var endpoint = this._generateEndpoint(options);
    var self = this;

    if (window.WebSocket) {
        this._connection = new WebSocket(endpoint);
    }
    else if (window.MozWebSocket) {
        this._connection = MozWebSocket(endpoint);
    }
    else {
        options.onError('WebSocket Not Supported');
        return ;
    }

    this._connection.onopen = function() {
        options.onConnect();
    };

    this._connection.onmessage = function (evt) {
        var data = JSON.parse(evt.data.toString());
        if (data.error !== undefined) {
            options.onError(data.error);
        }
        else if ( data.data ) {
            options.onData(data.data);
        }
    };

    this._connection.onclose = function(evt) {
        options.onClose();
    };
};

WSSHClient.prototype.send = function(data) {
    this._connection.send(JSON.stringify({'data': data}));
};
/**
 * Micro Hexapod control web interface app.
 **/

/**
 * This is a simple pub/sub bus defined on the window object to make it easy to
 * pass messages between different parts of the UI.
 *
 * See here: https://davidwalsh.name/pubsub-javascript
 * The window idea comes from here: https://dev.to/adancarrasco/implementing-pub-sub-in-javascript-3l2e
 *
 * Reading this makes my eyes bleed!!, but the principle is clear. JavaScript
 * sucks!!!
 *
 **/
window.pubSub = (function(){
    let topics = {};

    return {
        subscribe: function(topic, listener) {
            // Create the topic's object if not yet created
            if(!Object.hasOwn(topics, topic)) {
                //console.log("PUBSUB: Creating new topic '" + topic + "'.");
                topics[topic] = [];
            }

            // Add the listener to queue, recording it's index for possible
            // removal later
            let index = topics[topic].push(listener) - 1;
            //console.log("PUBSUB: New listener added to topic '" + topic + "': " + listener);

            // Provide handle back for removal of listener just added
            return {
                remove: function() {
                    //console.log("PUBSUB: Removing listener at index " + index + " from topic '" + topic + "'.");
                    delete topics[topic][index];
                }
            };
        },
        publish: function(topic, info) {
            // If the topic doesn't exist we simply return
            if(!Object.hasOwn(topics, topic)) {
                console.log("PUBSUB: Topic '" + topic + "' does not exist for publishing to.");
                return;
            }

            //console.log("PUBSUB: Publishinhg to topic '" + topic + "': " + info);

            // Cycle through topics queue and publish
            topics[topic].forEach(function(item) {
                item(info);
            });
        }
    };
})();

// This is the websocket URL to use depending on where we run from.
// We will try fetch it from localstorage, and default it to the location.host
// with '/ws/' appended as path if not stored.
let ws_url = localStorage.getItem('ws_url') || 'ws://' + location.host + '/ws';

// This will be the global websocket managed by the wsConnect function
let ws = null;

/**
 * Opens the modal dialog as the message type and displays the message
 * provided.
 **/
function popupMessage(msg, type=null, button="OK") {
    dialog = document.querySelector("dialog.msg");
    msg_div = dialog.querySelector("div.msg");
    button = dialog.querySelector("button");

    msg_div.innerHTML = msg;
    // Reset the class to only message to clear any previously added types
    dialog.classList = ['msg'];
    if (type) {
        dialog.classList.add(type);
    }
    dialog.showModal();
}

/**
 * On input event for the WebSocket URL input under the settings, as well as the
 * click event for the Test button in the same place.
 **/
function manageWebSockURL(event) {
    // The event is either click for the test button, of input for the input
    // field.
    switch (event.type) {
        case "input":
            // As soon as anything changes in the input field, we enable the
            // test button
            event.target.nextElementSibling.disabled = false;
            break;
        case "click":
            // Disable the button again.
            event.target.disabled = true;

            // The test/save button was clicked.
            // Get the value from the input field, and trim all whitespace
            // NOTE: It is expected that the input element is immediately before
            // the test button in the DOM.
            let url_val = event.target.previousElementSibling.value.trim()

           // Do very basic validation for the protocol and hostname
            if (! url_val.match(/^wss*:\/\/\w+/g)) {
                popupMessage(
                    "URL must start with <var>ws(s)://</var> " +
                    "followed by a host name and optional port and path.",
                    "err"
                );
                return;
            }

            // Save the URL and kick off a connect attempt.
            localStorage.setItem("ws_url", url_val);
            wsConnect();
            break;
    }
}

/**
 * Called when a navigation bar icon was clicked to change the active view.
 *
 * @param {event} event The JS click event
 * @param {str} func The expected function this click is to perform as a
 *        free form text string used to determine the acťion to perform.
 **/
function navChange(event) {
    // We get the function to do from the func data attribute on the target
    let func = event.target.dataset.func;

    // Find the section for this function
    let sect = document.querySelector(`div.sect.${func}`)
    if (! sect) {
        console.log(`Could not find a div.sect for : ${func}`);
        return;
    }

    // First switch off all sections
    document.querySelectorAll("div.sect").forEach(el => el.style.display = "none");

    // Now switch on the section for this function
    sect.style.display = "block";

    // And remove the active style from all nav items
    document.querySelectorAll("div.nav span").forEach(el => el.classList.remove("active"));
    // And set the current item to active
    event.target.classList.add("active");
}

/**
 * Called wherever a steer button is pressed.
 *
 * Args:
 *  event: The press event.
 *  dir: The direction: 'fwd', 'rev', 'rotr' or 'rotl'
 **/
function steerEvent(event, dir) {
    console.log(event);
    let opts = {
        'url': `${base_url}/steer`,
        'method': 'POST',
        'contentType': 'application/json',
        'data': JSON.stringify({'dir': dir})
    };

    console.log("Steering change:", dir);

    // Call the API to set the steering
    ajax(opts).then(
        // Success
        function(res) {
            // Remove the active state from all steer icons
            const ctrl = event.target.closest('div.control')
            ctrl.querySelectorAll('div.material-icons')
                .forEach(item => item.classList.remove('active'));
            // Make the clicked target active
            event.target.classList.add('active');
            // Set the steering angle
            const angle = ctrl.querySelector('input[name=angle]');
            angle.value = res.responseJSON.angle;
            angle.nextElementSibling.innerHTML = `${res.responseJSON.angle}${angle.dataset.unit}`;
        },
        // Error
        function(err) {
            popupMessage("Steer error: " + err, type='err');
        }
    );
}

/**
 * Updates the version display
 *
 * Args:
 *  version (str): The version as a string
 ***/
function updateVersion(version) {
    // Get the version element
    let elem = document.querySelector("div.app_version span");
    elem.textContent = version
}

/**
 * Updates the memory display for the remote
 *
 * Args:
 *  mem (str): The memory as "allocated:free" bytes
 ***/
function updateMemory(mem) {
    //TODO: Need to be implemented

    mem = mem.split(':')
    console.log(`Bot memory: allocated=${mem[0]}, free=${mem[1]}`);
    // Get the memory element
    //let elem = document.querySelector("div.app_version span");
    //elem.textContent = version
}

/**
 * Called to update the control UI elements to show the active steering
 * direction, the steer angle, the speed and stroke settings.
 **/
function updateControlUI() {
    // We'll be making API calls for each of the parts, but in future, it may
    // be good to have a single API call that returns all this in one go.

    // Get the outer control div elemt
    let control = document.querySelector("div.sect.control");

    // First the steer options
    let opts = {
        'url': `${base_url}/steer`,
        'method': 'GET',
        'contentType': 'application/json',
    };
    // Do it
    ajax(opts).then(
        // Success
        function(res) {
            console.log("Steer:", res.responseJSON);
            // First remove the active class from all direction icons
            control.querySelectorAll("div.material-icons")
                .forEach(ctrl => ctrl.classList.remove("active"));
            // Now set the correct direction to active
            control.querySelector(`div.grid-item.${res.responseJSON.dir}`).classList.add('active');
            // Get the angle slider element
            const angle = control.querySelector("div.grid-item.angle input")
            // Set it's angle value...
            angle.value = res.responseJSON.angle;
            // ...and also the angle indicator
            angle.nextElementSibling.innerText = `${angle.value}${angle.dataset.unit}`;
        },
        // Error
        function(err) {
            console.log("Steer error: ", err);
        }
    );

    // Function update any of the angle, speed or stroke sliders.
    function updateSlider(endpoint, cls_name, resp_name) {
        const opts = {
            'url': `${base_url}/${endpoint}`,
            'method': 'GET',
            'contentType': 'application/json',
        };
        // Do it
        ajax(opts).then(
            // Success
            function(res) {
                // Get the slider input element from the clas name
                const elem = control.querySelector(`div.grid-item.${cls_name} input`)
                console.log(`Updating ${elem.name}: ${res.responseJSON[resp_name]}`);
                // Set it's input value using the resp_name attribute we expect
                // in the response...
                elem.value = res.responseJSON[resp_name];
                // ...and also the angle indicator
                elem.nextElementSibling.innerText = `${elem.value}${elem.dataset.unit}`;
            },
            // Error
            function(err) {
                console.log("Stroke error: ", err);
            }
        );
    }

    // the speed
    updateSlider('speed', 'spd', 'speed');
    updateSlider('stroke', 'strk', 'stroke');
}

/**
 * Called when the pause / run button is clicked to toggle pause/run mode.
 **/
function playPauseEvent(event) {
    // Determine the new state by looking at the current button name.
    let new_state = event.target.innerText === "play_circle" ? "run" : "pause";

    pubSub.publish('motion', new_state);

    let opts = {
        'url': `${base_url}/${new_state}`,
        'method': 'POST',
        'contentType': 'application/json',
    };

    // Call the API to run or pause based on the desired new state
    ajax(opts).then(
        function(res) {
            console.log(res);
            // Update the button icon
            if (new_state === "pause") {
                event.target.innerText = "play_circle";
            } else {
                event.target.innerText = "pause_circle";
            }
        }
    );
}

/*################## TRIM HANDLING #################*/
/**
 * Gets the current trim values and updates the trim settings.
 **/
function getTrimSettings() {
    console.log("Requesting trim settings...");
    pubSub.publish('to_bot', {action: 'trim'});
}

/**
 * Called whenever a trim input setting is changed.
 * This only enables the trim settings "set" button if the value is valid.
 **/
function trimChanged(event) {
    // First check if the input is valid
    if (! event.target.checkValidity()) {
        console.log("Trim value is invalid. Disabling set button.");
        event.target.closest("div.trim").querySelector("button").disabled = true;
        return;
    }
    event.target.closest("div.trim").querySelector("button").disabled = false;
}

/**
 * Called when the trim set button is pressed.
 * Reads the current trim settings and publishes a trim set message.
 **/
function setTrims(event) {
    // First disable the update button. Any changes in trim settings will
    // enable it again
    event.target.disabled = true;

    // Read the trim values and construct the action argument
    let trims = ""
    event.target.parentElement.querySelectorAll("input").forEach(
        trim => {
            // Do not add a separator for the first value
            trims += (!trims ? "" : ":") + `${trim.value}`;
        }
    );
    // We want to force centering the servos after setting trims
    trims += ":true"

    // Now we publish a request to set them
    pubSub.publish('to_bot', {action: 'trim', args: trims});
}

/**
 * Callback for when we receive trims setting on the message Q.
 *
 * Args:
 *  val (str): "left:mid:right" or "err:Error message"
 **/
function updateTrims(val) {
    console.log("Received trims update: ", val);

    let vals;
    let elems;

    // Error?
    if (val.startsWith("err:")) {
        popupMessage(`Error setting trim values: ${val.replace(/^err:/,'')}.`, type='err')
        return;
    }
    vals = val.split(':');
    elems = document.querySelectorAll("div.sect.settings div.trim input");
    for (let idx=0; idx < elems.length; idx++) {
        elems[idx].value = vals[idx];
    }
}
/*################## END: TRIM HANDLING #################*/

/**
 * Called to center the servos
 **/
function centerServosEvent() {
    console.log("Centering servos");
    let opts = {
        'url': `${base_url}/center_servos`,
        'method': 'POST',
        'contentType': 'application/json',
        'data': JSON.stringify({'with_trim': true})
    };

    // Do it
    ajax(opts).then(
        // Success
        function(res) {
            // Force the play/pause button to be paused, i.e. show the play
            // button
            document.querySelector("div.control div.steer div.run").innerText = "play_circle";
        },
        // Error
        function(err) {
            console.log("Error: ", err);
        }
    );
}

/***
 * Called when a slider knob event happens.
 * This will show the value bubble, move it and update its value as the slider
 * is moved, and also hide it again when released.
 **/
function sliderEvent(event) {
    // The value div is expected to the next element after the target in the
    // DOM.
    const val_div = event.target.nextElementSibling;
    // Get the value in text format including the unit from the input element
    // data-unit attribute
    const val_txt = event.target.value + event.target.dataset.unit;

    switch (event.type) {
        case "input":
            val_div.textContent = val_txt;
            break;
        case "change":
            console.log(`Gonna set ${event.target.name} to ${event.target.value}`);
            // Set up the AJAX call
            let opts = {
                'url': `${base_url}/${event.target.dataset.endpoint}`,
                'method': 'POST',
                'contentType': 'application/json',
                // Since the key is a variable it needs to be in square
                // brackets to be evaluated as a string to be used as the key
                // \_(:-/)_/
                'data': JSON.stringify({[event.target.name]: parseInt(event.target.value, 10)})
            };

            // Call the API to run or pause based on the desired new state
            ajax(opts).then(
                function(res) {
                    console.log(res);
                }
            );
            break;
    }
}

/**
 * Called to attach all required event listeners to all range input sliders
 **/
function attachRangeSliderEvents() {
    const sliders = document.querySelectorAll("input[type=range]");
    sliders.forEach(slider => {
        // This fires every time the slider value changes and is used to update
        // the value display div
        slider.addEventListener("input", sliderEvent);
        // This fires on the final slider value when it comes to rest and is
        // used to make the API call.
        slider.addEventListener("change", sliderEvent);
    });
}

/**
 * Called when any of the sliders are changed
 **/
function sliderChange(event, measure) {
    console.log("Slider change: ", event);
    let val_elem = event.target.parentElement.querySelector('.val')

    val_elem.textContent = event.target.value + measure;
}

/**
 * Updates the obstacle distance indicator with a new distance value
 *
 * Args:
 *  dist (float): The distance measurement in mm. If null, then the distance
 *      indicator is hidden.
 **/
function updateObstacleDist(dist) {
    console.log("Updatinbg obtacle distance:", dist);
    let obst_elem = document.querySelector('div.steer div.grid-item.obst');
    let dist_elem = obst_elem.querySelector('div.dist');

    if (dist === 'clear') {
        obst_elem.style.display = "none";
        return;
    }

    // Make sure it's visibale in case it was hidden before.
    obst_elem.style.display = "block";
    dist_elem.textContent = Number(dist).toFixed(1);
}


/**
 * Called to connect the websocket.
 *
 * Will publish the following connection events on the [websock] topic via
 * the pubSub Q:
 *   - 'connected': If successfully connected to the remote WS
 *   - 'closed':    If the socket is closed. Also published if the
 *                  connection attempt fails.
 *   - 'already_conn': If already connected.
 *
 * Any messages arriving on the websock is expected to be in the
 * 'action:[args...]' format as defined by the Hexapod API. Once a message
 * arrives, the received args will be published as the message to the [action]
 * topic.
 **/
function wsConnect() {
    // Already connected?
    if (ws) {
        console.log('[WS]: already connected.');
        pubSub.published('websock', 'already_conn');
        return;
    }

    // Connect using the current host we loaded the site from.
    ws = new WebSocket(ws_url);

    // When the socket is connected, we publish the 'connected' message
    ws.onopen = function() {
        console.log('[WS]: connected.');
        pubSub.publish('websock', 'connected')
        // The close event gets called both for the initial connection attempt,
        // as well as when the connection is closed after it was opened
        // successfully before.
        // IN order to distinguish between the two events, we set a propery on
        // the websocket here to indicate that the connection was established
        // successfully. We can then check this property in the close event.
        ws.connectSuccess = true;
    };

    // When a new message
    ws.onmessage = function(msg) {
        //console.log('[WS]: message:', msg);
        // Split on colons so we can get the and optional args separately
        let args = msg.data.split(':');
        // Get the action out, leaving any optional args
        let action = args.shift()
        // Join the remaining args array with ':' again if it was split
        args = args.join(":")
        pubSub.publish(action, args)
    };

    ws.onclose = function(evt) {
        // See the comment in the open event for this property.
        let connectFail = !evt.target.connectSuccess;
        console.log(
            "[WS]: closed. " + (connectFail ? "Connection failed" : "Connection dropped")
        )
        ws = null;
        pubSub.publish('websock', 'closed:' + (connectFail ? 'fail' : 'drop'))
    };

    ws.onerror = function(evt) {
        if (ws.readyState == 1) {
            console.log(`[WS]: normal error: ${evt.type}`);
        }
    };
}

/**
 * Handle message received on the [to_bot] topic.
 *
 * These are messages containing actions to send to the hexapod.
 * The message is expected to be an object of the format:
 *
 *  {
 *     'action': "action",  // A valid hexapod action
 *     'args': ...          // Optional args required by the action
 *  }
 *
 * The action and args data will be combined in an 'action:[args...]' string
 * and sent on the websock to the hexapod via the websocket if connected. If
 * not connected and error will be logged to the console.
 *
 * If args is an object, it will be converted to a JSON string on the fly
 * before sending.
 *
 * Note that if args is undefined or null, no args will be sent.
 **/
function sendToHexapod(msg) {
    // We must have an action property
    if (!Object.hasOwn(msg, 'action')) {
        console.log(
            "Invalid message structure to send to hexapod. " +
            "No 'action' property: ", msg
        );
        return;
    }
    // Get the action
    dat = msg.action;
    // Do we need to convert the args object a JSON string?
    if (msg.args !== null && msg.args !== undefined && typeof msg.args === "object") {
        msg.args = JSON.stringify(msg.args);
    }
    // Only add the args if it is not undefined
    if (msg.args !== undefined) dat = dat + `:${msg.args}`;

    // Can we send it?
    if (!ws) {
        console.log(
            `Can not send message '${dat}' to hexapod because socket is ` +
            `not currently connected.`);
        return;
    }

    // Send it
    ws.send(dat);
}

/**
 * Called as soon as the connection to the hexapod API is established.
 **/
function remoteConnected() {
    // The URL is valid
    // Update the app version by requesting it from the remote
    pubSub.publish('to_bot', {action: 'version'});

    // When we're connected, the test button and WS URL input box must be
    // disabled.
    document.querySelector("div.settings label.ws_url input").disabled = true;
    document.querySelector("div.settings label.ws_url button").disabled = true;
    // Simulate a click of the control nav item to open that section by default
    let nav_item = document.querySelector("div.nav span[data-func=control]");
    // We need to dispatch a specific event to simulate the target being
    // passed in
    nav_item.dispatchEvent(new Event("click", {target: nav_item}));

    // Update the trim settings
    getTrimSettings();
    // Update the UI
    ////  updateControlUI();
}

/**
 * Called whenever the remote connection is closed, or we can not set up the
 * connection to start with.
 **/
function remoteDisconnected(reason) {
    console.log(`Websock connection down. Reason: ${reason}`);
    if (reason == "fail") {
        popupMessage(`Unable to connect to: [${ws_url}]. Please fix and try again.`, type='err')
    } else {
        popupMessage(`Connection to [${ws_url}] dropped. Please try to connect again.`, type='err')
    }
    // When we disconnect, we need to enable the WS URL input and the Test
    // button since these are now going to be needed.
    document.querySelector("div.settings label.ws_url input").disabled = false;
    document.querySelector("div.settings label.ws_url button").disabled = false;
    // Simulate a click of the settings nav item to open that section by default
    let nav_item = document.querySelector("div.nav span[data-func=settings]");
    // We need to dispatch a specific event to simulate the target being
    // passed in
    nav_item.dispatchEvent(new Event("click", {target: nav_item}));
}

/**
 * Called as the main function to start the app.
 **/
function main() {
    // Attach all event listeners to the input range sliders so we can react on
    // changes.
    attachRangeSliderEvents();

    // Preset the API base URL setting from base_url
    document.querySelector("div.sect.settings input[name=ws_url]").value = ws_url;

    // Create a handler to send all messages destined for the hexabot via the
    // websocket.
    pubSub.subscribe('to_bot', sendToHexapod)

    // Ping handler
    pubSub.subscribe('active', stat => {
        if (stat === 'ping')
            pubSub.publish('to_bot', {action: 'pong'});
    });
    // Updater for the version
    pubSub.subscribe('version', updateVersion);
    // Updater for the memory display
    pubSub.subscribe('memory', updateMemory);
    // Trim updater
    pubSub.subscribe('trim', updateTrims);


    // Monitor for websocket status
    pubSub.subscribe('websock', stat => {
        console.log('Websocket status: ', stat);
        switch (stat) {
            case 'connected':
                remoteConnected();
                break;
            case 'closed:fail':
            case 'closed:drop':
                remoteDisconnected(stat.split(':')[1])
                break;
            default:
                console.log(`No idea how to handle ${stat}`);
        }
    });

    wsConnect();
}

// Wait for the DOM to be loaded before our app starts.
document.addEventListener("DOMContentLoaded", main);

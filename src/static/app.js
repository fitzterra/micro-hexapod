/**
 * Micro Hexapod control web interface app.
 **/

/**
 * This is a simple pub/sub bus defined on the window object to make it easy to
 * pass messages between different parts of the UI.
 *
 * See here: https://davidwalsh.name/pubsub-javascript
 * 
 * The window idea comes from here:
 * https://dev.to/adancarrasco/implementing-pub-sub-in-javascript-3l2e
 *
 * Reading this makes my eyes bleed!!, but the principle is clear. JavaScript
 * sucks!!!
 *
 **/
window.Q = (function(){
    let topics = {};

    return {
        sub: function(topic, listener) {
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
        pub: function(topic, info) {
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
 * Opens a modal dialog as the message type and displays the message
 * provided.
 *
 * Expects a DOM element as follows to be present:
 *
 *     <dialog class="msg">
 *         <div class="msg"></div>
 *         <button onclick="event.target.closest('dialog').close();">
 *         </button>
 *     </dialog>
 * 
 * Args:
 *  msg (str): The message to display
 *  type (str): This will be added directly as a class to the <dialog> element
 *      which allows different dialog types (info, err, etc.) to be defined
 *      with CSS
 *  button (str): The action button text to show. Clicking this button will
 *      also close the dialog.
 *
 **/
function popupMessage(msg, type=null, button="OK") {
    dialog = document.querySelector("dialog.msg");
    msg_div = dialog.querySelector("div.msg");
    btn = dialog.querySelector("button");

    msg_div.innerHTML = msg;
    // Reset the class to only message to clear any previously added types
    dialog.classList = ['msg'];
    if (type) {
        dialog.classList.add(type);
    }
    // Set the button text
    btn.innerHTML = button;
    //Show it
    dialog.showModal();
}

/**
 * On input event handler for the WebSocket URL input under the settings, as
 * well as the click event for the Test button in the same place.
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
    mem = mem.replace(':', ' / ');
    console.log(`Bot memory: allocated/free: ${mem}`);
    // Get the memory element
    let elem = document.querySelector("div.info div.mem div.dat");
    elem.textContent = mem;
}

/**
 * Updates the oscillator state display
 *
 * Args:
 *  state (str): A JSON string with the current oscillator state settings.
 ***/
function updateOscState(state) {
    // First parse the JSON we receive to a proper list of list
    const oscState = JSON.parse(state);
    console.log('Oscillators state:', oscState);

    // Get the oscillator states table
    let table = document.querySelector("div.sect.oscState table");
    // These will be used to cycle over servos and their parameters
    let servo = 0;
    let param = 0;
    let cells;
    // Cycle through the available oscillators at the top level
    while (servo < oscState.length) {
        // Get a query set corresponding to the column of cells for all
        // parameters of this oscillator. Each row in the table has an initial
        // <th> elements, and the nth-child selector is 1 based, so we need to
        // add 2 to get to the correct row level <td> cell
        cells = table.querySelectorAll(`tr td:nth-child(${servo+2})`)
        // Reset the parameter counter
        param = 0;
        // Cycle through all oscillator parameters, dropping them in each
        // column cell.
        while (param < oscState[servo].length) {
            cells[param].textContent = oscState[servo][param];
            param++;
        }
        servo++;
    }
}

/*################## MOTION HANDLING #################*/
/**
 * Callback for when we receive a motion update - either run or pause.
 *
 * Note this indicates the current motion setting on the Hexapod. Since the
 * button we are managing for this is a toggel, it needs to be set to the
 * opposite state as the current state we received.
 *
 * Args:
 *  val (str): "run|pause" or "err:Error message"
 **/
function updateMotion(val) {
    console.log("Received motion state: ", val);

    let elem;

    // Error?
    if (val.startsWith("err:")) {
        popupMessage(`Error in motion control: ${val.replace(/^err:/,'')}.`, type='err')
        return;
    }
    // Get the run/pause div element
    elem = document.querySelector("div.sect.control div.run");
    // Set the data-next attribute as well as the icon to use
    if (val === 'run') {
        // Currently in the run state, so we need to set the button to become a
        // pause button
        elem.dataset.next = 'pause';
        elem.innerText = "pause_circle";
    } else {
        // Currently in the pause state, so we need to set the button to become a
        // run button
        elem.dataset.next = 'run';
        elem.innerText = "play_circle";
    }
}
/*################## END: MOTION HANDLING #################*/

/*################## STEERING HANDLING #################*/
/**
 * Callback for when we receive a direction update.
 *
 * Note this indicates the current steer or rotation direction setting on the
 * Hexapod.
 *
 * Args:
 *  val (str): "fwd|rev|rotr|rotl" or "err:Error message"
 **/
function updateDirection(val) {
    console.log("Received direction state: ", val);

    let elems;

    // Error?
    if (val.startsWith("err:")) {
        popupMessage(`Error in motion control: ${val.replace(/^err:/,'')}.`, type='err')
        return;
    }
    // Remove the active state from all steer icons
    elems = document.querySelector("div.sect.control");
    elems.querySelectorAll('div.material-icons')
        .forEach(item => item.classList.remove('active'));
    // Activate the current steer direction
    elems.querySelector(`div.${val}.material-icons`).classList.add('active');
}

/**
 * Callback for when we receive a steering angle update.
 *
 * Note this indicates the current steer angle on the Hexapod.
 *
 * Args:
 *  val (str): "[-]int" or "err:Error message"
 **/
function updateAngle(val) {
    console.log("Received steer angle value: ", val);

    let elem;

    // Error?
    if (val.startsWith("err:")) {
        popupMessage(`Error in motion control: ${val.replace(/^err:/,'')}.`, type='err')
        return;
    }
    // Find the angle slider input element
    elem = document.querySelector("div.sect.control input[name=angle]");
    // Set the value on the slider
    elem.value = val;
    // And also the numeric angle indicator using the default unit
    elem.nextElementSibling.innerHTML = `${val}${elem.dataset.unit}`;
}

/**
 * Callback for when we receive a speed percentage update.
 *
 * Note this indicates the current speed percentage on the Hexapod.
 *
 * Args:
 *  val (str): "int" or "err:Error message"
 **/
function updateSpeed(val) {
    console.log("Received speed percentage: ", val);

    let elem;

    // Error?
    if (val.startsWith("err:")) {
        popupMessage(`Error in speed setting: ${val.replace(/^err:/,'')}.`, type='err')
        return;
    }
    // Find the speed slider input element
    elem = document.querySelector("div.sect.control input[name=speed]");
    // Set the value on the slider
    elem.value = val;
    // And also the numeric angle indicator using the default unit
    elem.nextElementSibling.innerHTML = `${val}${elem.dataset.unit}`;
}
/**
 * Callback for when we receive a stroke percentage update.
 *
 * Note this indicates the current stroke percentage on the Hexapod.
 *
 * Args:
 *  val (str): "int" or "err:Error message"
 **/
function updateStroke(val) {
    console.log("Received stroke percentage: ", val);

    let elem;

    // Error?
    if (val.startsWith("err:")) {
        popupMessage(`Error in stroke setting: ${val.replace(/^err:/,'')}.`, type='err')
        return;
    }
    // Find the speed slider input element
    elem = document.querySelector("div.sect.control input[name=stroke]");
    // Set the value on the slider
    elem.value = val;
    // And also the numeric angle indicator using the default unit
    elem.nextElementSibling.innerHTML = `${val}${elem.dataset.unit}`;
}
/*################## END: STEERING HANDLING #################*/

/*################## TRIM HANDLING #################*/
/**
 * Gets the current trim values and updates the trim settings.
 **/
function getTrimSettings() {
    console.log("Requesting trim settings...");
    Q.pub('to_bot', 'trim');
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
    Q.pub('to_bot', {action: 'trim', args: trims});
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
    // The value div is expected to be the next element after the target in the
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
            // Send the command
            Q.pub('to_bot', {action: event.target.dataset.action, args: event.target.value});
            break;
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
 * Updates the obstacle distance indicator with a new distance value is
 * received, or if the detection state is switched on or off.
 *
 * Args:
 *  dist (float|str): One of the following:
 *      * 'on'    - obstacle detection is switched on
 *      * 'off'   - obstacle detection is switched off
 *      * 'clear' - a previously detected obstacle has cleared
 *      * int     - an obstacle has been detected at this distance in mm
 **/
function updateObstacleDist(dist) {
    console.log("Updatinbg obtacle distance:", dist);
    let obst_elem = document.querySelector('div.steer div.grid-item.obst');
    let dist_elem = obst_elem.querySelector('div.dist');

    if (dist == 'on') {
        obst_elem.classList.remove('off');
        return;
    }
    if (dist == 'off') {
        obst_elem.classList.add('off');
        obst_elem.classList.add('clear');
        dist_elem.textContent = '';
        return;
    }

    if (dist === 'clear') {
        obst_elem.classList.add('clear');
        dist_elem.textContent = '';
        return;
    }

    // We're not clear anymore, and we update the distance.
    obst_elem.classList.remove('clear');
    dist_elem.textContent = Number(dist).toFixed(1);
}


/**
 * Called to connect the websocket.
 *
 * Will publish the following connection events on the [websock] topic via
 * the Q Q:
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
        Q.pub('websock', 'already_conn');
        return;
    }

    // Connect using the current host we loaded the site from.
    ws = new WebSocket(ws_url);

    // When the socket is connected, we publish the 'connected' message
    ws.onopen = function() {
        console.log('[WS]: connected.');
        Q.pub('websock', 'connected')
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
        Q.pub(action, args)
    };

    ws.onclose = function(evt) {
        // See the comment in the open event for this property.
        let connectFail = !evt.target.connectSuccess;
        console.log(
            "[WS]: closed. " + (connectFail ? "Connection failed" : "Connection dropped")
        )
        ws = null;
        Q.pub('websock', 'closed:' + (connectFail ? 'fail' : 'drop'))
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
 * The action and args data will be combined in an 'action[:args...]' string
 * and sent on the websock to the hexapod via the websocket if connected. If
 * not connected and error will be logged to the console.
 *
 * If args is an object, it will be converted to a JSON string on the fly
 * before sending.
 *
 * Note that if args is undefined or null, no args will be sent.
 *
 * If the action does not need any args, then msg can just be a string and it
 * will be sent as is.
 **/
function sendToHexapod(msg) {
    let dat;
    let args = undefined;

    if (typeof msg === "string") {
        dat = msg;
    } else {
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
            args = JSON.stringify(msg.args);
        } else {
            args = msg.args;
        }
    }

    // Only add the args if it is not undefined
    if (args !== undefined) dat = dat + `:${args}`;

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
    Q.pub('to_bot', 'version');

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
    //getTrimSettings();
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
    Q.sub('to_bot', sendToHexapod)

    // Ping handler
    Q.sub('active', stat => {
        if (stat === 'ping')
            Q.pub('to_bot', 'pong');
    });
    // Updater for the version
    Q.sub('version', updateVersion);
    // Updater for the memory display
    Q.sub('memory', updateMemory);
    // Handler for the oscillator state response
    Q.sub('osc', updateOscState);
    // Trim updater
    Q.sub('trim', updateTrims);
    // Motion updater
    Q.sub('motion', updateMotion);
    // Steer direction updater
    Q.sub('dir', updateDirection);
    // Steer angle updater
    Q.sub('angle', updateAngle);
    // Speed updater
    Q.sub('speed', updateSpeed);
    // Stroke updater
    Q.sub('stroke', updateStroke);
    // Obstacle detection
    Q.sub('obst', updateObstacleDist);

    // Monitor for websocket status
    Q.sub('websock', stat => {
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

/**
 * Micro Hexapod control web interface app.
 */

// This is the base URL to use depending on where we run from.
// We will try fetch it from localstorage, and default it to the empty string
// if not stored.
let base_url = localStorage.getItem('base_url') || '';


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
 * On input event for the API base URL input under the settings, as well as the
 * click event for the Test button in the same place.
 **/
function manageBaseURL(event) {
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

            // If empty, then we will use the site base address, else it has to start
            // with http(s):// followed by some host name
            if (! url_val.match(/^$|^https*:\/\/\w+/g)) {
                popupMessage(
                    "URL must be empty, or start with <var>http(s)://</var> " +
                    "followed by a host name and optional port.",
                    "err"
                );
                return;
            }

            // Remove trailing slash if present
            url_val = url_val.replace(/\/*$/, '');  /* */

            // To test, we call the /mem endpoint using the new base URL value
            ajax({url: `${url_val}/mem`}).then(
                // Success
                function(res) {
                    popupMessage("It verks!!");
                    // Set the global new base_url and also save it to
                    // local storage.
                    base_url = url_val;
                    localStorage.setItem("base_url", url_val);
                    // Also get the trim settings from the new API host
                    getTrimSettings();
                    // ...and update the control UI
                    updateControlUI();
                },
                // Error
                function(err) {
                    console.log("Invalid URL:<br>", err);
                    popupMessage(err, "err");
                }
            );
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
 * Called to fetch and update the app version
 ***/
function updateVersion() {
    // Get the version element
    let version = document.querySelector("div.app_version span");

    // set the call options
    let opts = {
        'url': `${base_url}/version`,
        'method': 'GET',
        'contentType': 'application/json',
    };
    // Do it
    ajax(opts).then(
        // Success
        function(res) {
            console.log("Vesion:", res.responseJSON);
            version.textContent = res.responseJSON.version;
        },
        // Error
        function(err) {
            console.log("Version error: ", err);
        }
    );
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

/**
 * Gets the current trim values and updates the trim settings.
 **/
function getTrimSettings() {
    console.log("Getting trim settins...")
    let opts = {
        'url': `${base_url}/trim`,
        'method': 'GET',
        'contentType': 'application/json',
    };

    // Do it
    ajax(opts).then(
        // Success
        function(res) {
            const trim_settings = res.responseJSON;
            // We assume the trim settings comes back as left, mid right, and
            // that the trim inputs in the DOM are in the same order.
            const trim_inputs = document.querySelectorAll("div.sect.settings div.trim input")
            for (let i = 0; i < trim_inputs.length; i++) {
                console.log(`Updating ${trim_inputs[i].name} from ${trim_inputs[i].value} to ${trim_settings[i]}`);
                trim_inputs[i].value = trim_settings[i];
            }
        },
        // Error
        function(err) {
            console.log("Error: ", err);
        }
    );
}

/**
 * Called whenever a trim setting is changed.
 * This only enables the trim settings update button.
 **/
function trimChanged(event) {
    console.log(event);
    event.target.closest("div.trim").querySelector("button").disabled = false;
}

/**
 * Called when the trim update button is pressed.
 * Reads the current triom settings, calls the API to update them, and disables
 * the button.
 **/
function updateTrims(event) {
    // First disable the update button. Any changes in trim settings will
    // enable it again
    event.target.disabled = true;

    // Read the trim values
    let trims = [];
    event.target.parentElement.querySelectorAll("input").forEach(
        trim => {
            trims.push(parseInt(trim.value, 10));
        }
    );

    // Now we call the API to set them
    let opts = {
        'url': `${base_url}/trim`,
        'method': 'POST',
        'contentType': 'application/json',
        'data': JSON.stringify({"trim": trims, "center": true}),
    };

    // Call the API to run or pause based on the desired new state
    ajax(opts).then(
        // Success
        function(res) {
            console.log(res);
        },
        // Error
        function(err) {
            console.log(err);
        }
    );
}

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
 * Tests if the API URL (base_url) is valid by calling the /mem endpoint.
 *
 * It returns a promise where .then can be used to test for true, or an error
 * string if the URL is invalid"
 *
 * testAPIURL().then(
 *      res => {
 *          if (res === true) {
 *              console.log("URL is valid.");
 *          } else {
 *              console.log("URL is not valid. Error:", res);
 *          }
 *
 *      }
 * );
 *
 **/
function testAPIURL() {
    return ajax({url: `${base_url}/mem`}).then(
        // Success
        function(res) {
            return(true);
        },
        // Error
        function(err) {
            return(err);
        }
    );
}

/**
 * Called as the main function to start the app.
 **/
function main() {
    // Attach all event listeners to the input range sliders so we can react on
    // changes and to show a nice little bubble to help you find the right
    // value to set it to.
    attachRangeSliderEvents();

    // Preset the API base URL setting from base_url
    document.querySelector("div.sect.settings input[name=base_url]").value = base_url;

    // Test that the URL is valid
    testAPIURL().then(
        res => {
            if (res === true) {
                // The URL is valid
                // Update the app version
                updateVersion();

                // Simulate a click of the control nav item to open that section by default
                let nav_item = document.querySelector("div.nav span[data-func=control]");
                // We need to dispatch a specific event to simulate the target being
                // passed in
                nav_item.dispatchEvent(new Event("click", {target: nav_item}));

                // Update the trim settings
                getTrimSettings();
                // Update the UI
                updateControlUI();
            } else {
                popupMessage(`The API URL [${base_url}] is invalid. Please fix before continuing.`, type='err')
                // Simulate a click of the settings nav item to open that section by default
                let nav_item = document.querySelector("div.nav span[data-func=settings]");
                // We need to dispatch a specific event to simulate the target being
                // passed in
                nav_item.dispatchEvent(new Event("click", {target: nav_item}));
            }
        }
    );
}

document.addEventListener("DOMContentLoaded", main);

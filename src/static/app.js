/**
 * Micro Hexapod control web interface app.
 */

//
base_url = 'http://192.168.1.201'

// Will be initialized in main()
let hexapod = null;

/**
 * A Hexapod object containing all properties and methods to control the
 * hexapod over the REST API.
 **/
class Hexapod {
    // The current hexapod params as received from a call to /get_params. Will
    // be updated on instantiation, and also from local input.
    params = null;

    /**
     * The instance constructor method.
     *
     * It only calls the fetchParams method;
     * state is paused.
     **/
    constructor() {
        this.fetchParams()

    }

    /**
     * Fetches the current hexapod parameters and saves it localy and updates
     * the view
     **/
    fetchParams() {
        // Make the call
        ajax({'url': `${base_url}/get_params`}).then(
            (req) => {
                this.params = req.responseJSON;
            }
        ).then(
            function() {
                updateParamsView();
            }
        );
    }

    /**
     * Sets the hexapod parameters to what is in this.params.
     *
     * This is normally called after updating one of the params from local
     * input to update the same on the backend.
     **/
    setParams(callback=null) {
        // Set the ajax options
        let opts = {
            'url': `${base_url}/set_params`,
            'method': 'POST',
            'contentType': 'application/json',
            'data': JSON.stringify(this.params),
        };

        // Make the call
        ajax(opts).then(
            (req) => {
                let resp = req.responseJSON;
                if (! resp.success) {
                    console.log("Error setting parameter:", resp.errors);
                }
            }
        ).then(
            () => {
                if (callback!==null) {
                    callback();
                }
            }
        );
    }

    /**
     * Sets the hexapod speed.
     *
     * This method will set set the speed param and then call setParams.
     **/
    speed(spd) {
        this.params.speed = spd;

        this.setParams();
    }

    /**
     * Sets the stokes for the leg servos.
     *
     * This method will set set the stroke param and then call setParams.
     **/
    stroke(strk) {
        this.params.stroke = strk;

        this.setParams();
    }

    /**
     * Toggles run/pause
     **/
    pauseToggle() {
        this.params.paused = !this.params.paused;

        this.setParams();
    }

    /**
     * Centers all servos
     **/
    centerServos() {
        console.log("Centering servos.");
        // Make the call
        ajax({'url': `${base_url}/center_servos`}).then(
            (req) => {
                this.params = req.responseJSON;
            }
        ).then(
            function() {
                updateParamsView();
            }
        );
    }

    /**
     * Save the current parameters to persistent storage
     **/
    saveParams() {
        console.log("Saving params.");
        // Make the call
        ajax({'url': `${base_url}/save_params`}).then(
            (req) => {
                this.params = req.responseJSON;
            }
        ).then(
            function() {
                updateParamsView();
            }
        );
    }

    /**
     * Steers the hexapod.
     *
     * Args:
     *  direct: Optional one of 'fwd', rev', left' or 'right'
     *  angle: Optional between -180 and 180, with 0 being forward, 90 = right,
     *          -90 = left and 180 or -180 = reverse. Anything in between will
     *          turn in that direction more or less sharp ????
     *  callback: Optional callback to call with results of API call.
     **/
    steer(direct=null, angle=null, callback=null) {
        console.log(`Steering - direct: ${direct}, angle: ${angle}, callback: ${callback}`);
        // Set the ajax options
        let opts = {
            'url': `${base_url}/steer`,
            'method': 'POST',
            'contentType': 'application/json',
            'data': JSON.stringify({"direct": direct, "angle": angle}),
        };

        // Make the call
        ajax(opts).then(
            (req) => {
                let resp = req.responseJSON;
                if (! resp.success) {
                    console.log("Error in steer call:", resp.errors);
                }
                this.params = resp.params;
            }
        ).then(
            function() {
                updateParamsView();
            }
        ).then(
            () => {
                if (callback!==null) {
                    callback();
                }
            }
        );
    }
}

/**
 * Called to update a range slider bubble with the current value.
 **/
function setRangeBubble(range, bubble) {
  const val = range.value;
  const min = range.min ? range.min : 0;
  const max = range.max ? range.max : 100;
  const newVal = Number(((val - min) * 100) / (max - min));
  bubble.innerHTML = val;

  // Sorta magic numbers based on size of the native UI thumb
  bubble.style.left = `calc(${newVal}% + (${8 - newVal * 0.15}px))`;
}

/**
 * Called when a range slider value was changed to the final value.
 * Receives the event as argument from which the slider name can be retrieved.
 *
 * If the name of the slider element is "speed", then the setParam method will
 * be called to send the new speed value to the hexapod.
 **/
function rangeChanged(event) {
    let param = event.target.name;
    let value = event.target.valueAsNumber;

    console.log("Slider changed", param, "to", value);

    // Is it a speed change?
    if (param === "speed") {
        hexapod.speed(value);
    }
    // Is it a stroke change?
    if (param === "stroke") {
        hexapod.stroke(value);
    }
}

/**
 * Called when a navigation bar icon was clicked to change the active view.
 *
 * @param {event} event The JS click event
 * @param {str} func The expected function this click is to perform as a
 *        free form text string used to determine the acťion to perform.
 **/
function navChange(event, func) {
    // From the click target, find the closest div.sect parent. This is the
    // section the clicked happen in.
    let sect = event.target.closest("div.sect")
    if (! sect) {
        conslole.log("Could not find a parent div.sect for click target: ", event.target);
        return;
    }

    // Navigation between config, status or fw_update views?
    if (func === "config" || func === "home" || func == "fw_update") {
        // The func value is the section to be switched on, which will be a
        // div element with 'sect' class to indicate it's a section, and also
        // the functionality class which is what we get in func. Combine these
        // to get a DOM selector for the div section that is going to be
        // switched on.
        let switch_on = `div.sect.${func}`;

        // The current section we're in needs to be switched off, and the other
        // switched on.
        sect.style.display = "none";
        let target_sect = document.querySelector(switch_on);
        target_sect.style.display = "inline";

        // If going to config, also refresh the config automatically.
        if (func == "config") {
            refreshConfig();
        } else if (func == "fw_update") {
            // We empty the log div and hide
            target_sect.querySelector("pre.log_data").textContent = ""
            target_sect.querySelector("pre.log_data").style.display = "none";

            // We display the update_log button
            target_sect.querySelector("button.update_log").style.display = "inline-block";
        }
        
        return;
    }

    // Refresh the config view?
    if (func === "refresh" ) {
        // Remove any error blinker class added previously on save error
        event.target.classList.remove("err_blinker");
        if (sect.classList.contains("config")) {
            refreshConfig();
        } else {
            refreshStatus(updateStatus);
        }
        return;
    }

    console.log(`Uknow navigation function: ${func}`);
}

/**
 * Called when the pause / run button is clicked to toggle pause/run mode.
 **/
function pauseToggle(event) {
    hexapod.pauseToggle();

    // Update the button icon
    if (hexapod.params.paused) {
        event.target.innerText = "play_circle";
    } else {
        event.target.innerText = "pause_circle";
    }
}


/**
 * Called wherever a trim or phase input is changed.
 **/
function inputChanged(event) {
    // To know if this is a trim, phase_shift or amplitude input change, we
    // need the class name of the closest parent <tr>.
    let param = event.target.closest("tr").className;
    // The input element name is the servo that has to change, left, mid or
    // right
    let servo = event.target.name;
    // And the new value
    let val = event.target.valueAsNumber;

    console.log(`Changing ${servo} servo ${param} to ${val}`);
    
    // Do it, and then update the hexapod
    hexapod.params['servo'][servo][param] = val;
    hexapod.setParams();
}

/**
 * Finds all number input controls in the servo control table and binds their
 * onchange event to the inputChanged method.
 **/
function bindInputChanges() {
    let input = null;

    document.querySelectorAll("div.servo tr input[type=number]").forEach((input) => {
        input.addEventListener('change', inputChanged);
    });
}

/**
 * This function can be called to update the control parameter arguments from
 * the params values from the hexapod instance.
 **/
function updateParamsView() {
    // First zoom in on the control section
    let sect = document.querySelector("div.sect.control");
    
    // Lets start with the pause/run button
    let target = sect.querySelector("tr.controls span.playpause");
    if (hexapod.params.paused) {
        target.innerText = "play_circle";
    } else {
        target.innerText = "pause_circle";
    }

    // Now the speed
    target = sect.querySelector("tr.speed input");
    target.value = hexapod.params.speed;
    // And trigger the change event to update the bubble
    target.dispatchEvent(new Event('input'));

    // And the stroke
    target = sect.querySelector("tr.stroke input");
    target.value = hexapod.params.stroke;
    // And trigger the change event to update the bubble
    target.dispatchEvent(new Event('input'));

    // Now the trim, phase_shift and amplitude inputs
    // And the trim
    let input, param, servo;
    // These parameters are number type inputs, one params per table row inside
    // the servo div.
    document.querySelectorAll("div.servo tr input[type=number]").
        forEach((input) => {
            // The parameter (trim, phase_shift or amplitude we get from the
            // closest parent tr element
            param=input.closest("tr").className;
            // The servo we are targeting is the input name
            servo=input.name;
            // Set the input value from the hexapod params
            input.value = hexapod.params.servo[servo][param];
        });
}


/**
 * Called as the main function to start the app.
 **/
function main() {

    // Sets up the range slider bubbles and also an event listener to call when
    // the range value slider settles on the final value.
    let allRanges = document.querySelectorAll(".range-wrap");
    allRanges.forEach(wrap => {
        const range = wrap.querySelector(".range");
        const bubble = wrap.querySelector(".bubble");

        range.addEventListener("input", () => {
            setRangeBubble(range, bubble);
        });
        setRangeBubble(range, bubble);

        range.addEventListener("change", rangeChanged);
    });

    // Bind the trim and phase inputs
    bindInputChanges();

    // Create an instance of the hexapod controller
    hexapod = new Hexapod();
}

document.addEventListener("DOMContentLoaded", main);

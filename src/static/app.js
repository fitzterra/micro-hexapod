/**
 * Micro Hexapod control web interface app.
 */

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
     * Fetches the current hexapod parameters and sets this.params
     **/
    fetchParams() {
        // Make the call
        ajax({'url': '/get_params'}).then(
            function(req) {
                this.params = req.responseJSON;
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
function rangeCanged(event) {
    let param = event.target.name;
    let value = event.target.valueAsNumber;

    console.log("Slider changed", param, "to", value);

    // Is it a speed change?
    if (param === "speed") {
        setParam(param, value);
    }
}

/**
 * Function set any supported Hexapod parameter.
 *
 * This calls the /set API method and POSTs the JSON from args as:
 *  {param: value}
 *
 * See the API method docs for more details.
 *
 */
function setParam(param, value) {

    let params = {
        [param]: value
    };
    // Set the ajax options
    let opts = {
        'url': '/set_params',
        'method': 'POST',
        'contentType': 'application/json',
        'data': JSON.stringify(params),
    };

    // Make the call
    ajax(opts).then(
        function(req) {
            resp = req.responseJSON;
            if (! resp.success) {
                console.log("Error setting parameter:", resp.errors);
            }
        }
    );
}

/**
 * Called when the play/pause button is clicked to pause or run the hexapod.
 **/

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
 * Called as the main function to start the app.
 **/
function main() {

    // Sets up the range slider bubbles and also an event listener to call when
    // the final range value is set.
    let allRanges = document.querySelectorAll(".range-wrap");
    allRanges.forEach(wrap => {
        const range = wrap.querySelector(".range");
        const bubble = wrap.querySelector(".bubble");

        range.addEventListener("input", () => {
            setRangeBubble(range, bubble);
        });
        setRangeBubble(range, bubble);

        range.addEventListener("change", rangeCanged);
    });

    hexapod = new Hexapod();

    // Add an event listener to the button
    //document.querySelector("div.control button.valve").
    //    addEventListener('click', valveAction);

    //refreshStatus(updateStatus);

}

document.addEventListener("DOMContentLoaded", main);

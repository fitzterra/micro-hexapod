/**
 * Micro Hexapod control web interface app.
 */

// This is the base URL to use depending on where we run from
let base_url = '';

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

    // Call the API to run or pause based on the desired new state
    ajax(opts).then(
        function(res) {
            console.log(res);
        }
    );
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
 * Called as the main function to start the app.
 **/
function main() {
    // Attach all event listeners to the input range sliders so we can react on
    // changes and to show a nice little bubble to help you find the right
    // value to set it to.
    attachRangeSliderEvents();

    // Simulate a click of the control nav item to open that section by default
    let nav_item = document.querySelector("div.nav span[data-func=control]");
    // We need to dispatch a specific event to simulate the target being
    // passed in
    nav_item.dispatchEvent(new Event("click", {target: nav_item}));
}

document.addEventListener("DOMContentLoaded", main);

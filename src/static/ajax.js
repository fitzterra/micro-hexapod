/**
 * Minimal Ajax library
 * @param  {object} options Options
 * @param  {string} options.url Url
 * @param  {string} [options.method='GET'] Method GET|POST|PUT|DELTE
 * @param  {string} [options.data] Body of the request
 * @param  {string} [options.contentType='application/x-www-form-urlencoded'] Set the content type of the body
 * @param  {number} [options.timeout] Timout in milliseconds
 * @param  {boolean} [options.withCredentials=false] withCredentials
 * @return {Promise} Returns a promise
 * @author Victor N <victornunes@lett.digital> 
 * @source https://gist.github.com/victornpb/689f88cf6d0121363ffbb01e86777c9c
 */
function ajax(options) {
    return new Promise(function (resolve, reject) {
        var xhr = (function(){
            try { return new XMLHttpRequest();}
            catch (e) {
                try { return new ActiveXObject('Msxml2.XMLHTTP');}
                catch (e) {
                    try { return new ActiveXObject('Microsoft.XMLHTTP');}
            catch(e){reject(new Error('Ajax: XMLHttpRequest not supported'));}}}
        })();
    
        var requestTimeout = options.timeout ? setTimeout(function() {
          xhr.abort();
          reject(new Error('Ajax: aborted by timeout'));
        }, options.timeout) : null;
        
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== 4) return;
            clearTimeout(requestTimeout);
            if (xhr.status >= 200 && xhr.status < 300) {

                try {
                    // if (/application\/json/.test(xhr.getResponseHeader('content-type'))) {
                        xhr.responseJSON = JSON.parse(xhr.responseText); //try to parse anyways
                    // }
                } catch (err) {}
                resolve(xhr, xhr.responseJSON || xhr.responseText);
            }
            else {
                reject(new Error('Ajax: server response status is ' + xhr.status));
            }
        };
        xhr.open(options.method ? options.method.toUpperCase() : 'GET', options.url, true);
      
        if(options.withCredentials) xhr.withCredentials = true;
      
        if (!options.data) xhr.send();
        else {
          xhr.setRequestHeader(
            'Content-Type',
            options.contentType ? options.contentType : 'application/x-www-form-urlencoded'
          );
          xhr.send(options.data);
        }
    });
}

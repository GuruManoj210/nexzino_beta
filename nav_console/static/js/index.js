// How long to show the loading spinner before redirecting after starting
// mapping/navigation. The original app waited for a specific rosout log
// message ("Initialization complete" / "odom received!") published by
// turtlebot3/mr_carter-specific nodes that don't exist in this stack - that
// wait would never resolve here, so this just uses a fixed delay instead
// (the original already had this as a fallback timeout; it's now the only
// mechanism).
const STARTUP_DELAY_MS = 8000;

$(document).ready(function() {

    $body = $("body");

    $("#index-map").click(function(event) {
        $body.addClass("loading");
        $.ajax({
            url: '/navigation/index',
            type: 'POST',
            success: function(response) {
                console.log(response);
                setTimeout(function() {
                    window.location = "/mapping";
                    $body.removeClass("loading");
                }, STARTUP_DELAY_MS);
            },
            error: function(error) {
                console.log(error);
                $body.removeClass("loading");
            }

        })
    });

    $("#index-list").click(function(event) {
        document.cookie = event.target.innerHTML;
        $('#exampleModal').modal('hide');


        $.ajax({

            url: '/index/navigation-precheck',
            type: 'GET',
            success: function(response) {


                if (response.mapcount > 0) {

                    $body.addClass("loading");

                    $.ajax({

                        url: '/index/gotonavigation',

                        type: 'POST',

                        data: event.target.innerHTML,

                        success: function(response) {
                            setTimeout(function() {
                                window.location = "/navigation";
                                $body.removeClass("loading");
                            }, STARTUP_DELAY_MS);
                        },
                        error: function(error) {
                            console.log(error);
                            $body.removeClass("loading");
                        }

                    })


                } else {
                    alert("No map in directory.Please do mapping.")
                }
            },
            error: function(error) {
                console.log(error);
            }

        })
    });


});

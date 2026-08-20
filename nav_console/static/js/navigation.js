var navigation = false;
var pathed = false;
var homing = false;
var MAP_WIDTH = (window.innerWidth) * 0.65;
var MAP_HEIGHT = window.innerHeight - (window.innerHeight) * 0.08;
var value = document.cookie;
// See index.js for why this replaced the original rosout-message wait.
var STARTUP_DELAY_MS = 8000;



$("#drop-text").change(function() {
    alert($("#drop-text :selected").text())
});
$(document).ready(function() {
    $body = $("body");
    $(".dropdown-content a").click(function(event) {
        $body = $("body");
        event.preventDefault();
        robotvisible = true;


        value = event.target.firstChild.data
        imageurl(value)
        $.ajax({
            url: '/navigation/loadmap',
            type: 'POST',
            data: value,
            success: function(response) {
                console.log(response);
            },
            error: function(error) {
                console.log(error);
            }

        })
        $body.addClass("loading");
        setTimeout(function() {
            $body.removeClass("loading");
        }, STARTUP_DELAY_MS);

    });

    window.imageurl = function(value) {

        NAV2D.ImageMapClientNav({
            ros: ros,
            viewer: viewer,
            rootObject: viewer.scene,
            serverName: '/move_base',
            image: `/static/maps/${value}.png`
        });
    }



    // ws://0.0.0.0:9090 only ever works if the browser happens to be on the
    // same machine as rosbridge - from any other machine (the normal case
    // here, same as servo_tester/web_teleop) it tries to connect to the
    // BROWSER's own machine instead of the robot. Derive the host from the
    // URL actually used to load this page instead.
    var ros = new ROSLIB.Ros({
        url: 'ws://' + window.location.hostname + ':9090'
    });

    // web_video_server (port 8080) re-streams /camera/color/image_raw as
    // MJPEG - same hostname-derivation reasoning as the rosbridge URL above.
    document.getElementById('camera-stream').src =
        'http://' + window.location.hostname + ':8080/stream?topic=/camera/color/image_raw';

    // Create the main viewer.
    var viewer = new ROS2D.Viewer({
        divID: 'nav',
        width: MAP_WIDTH,
        height: MAP_HEIGHT
    });



    var imageMapClientNav = new NAV2D.ImageMapClientNav({
        ros: ros,
        viewer: viewer,
        rootObject: viewer.scene,
        serverName: '/move_base',
        image: `/static/maps/${value}.png`
    });




    gridClient = new NAV2D.OccupancyGridClientNav({
        ros: ros,
        rootObject: viewer.scene,
        viewer: viewer,
        serverName: '/move_base',
        continuous: true
    });

    function mapchangegraphical() {

        imageMapClientNav.addImg();
    };


    function mapchangelive() {

        imageMapClientNav.removeImg();

    }
    var pan = new ROS2D.PanView({
        ros: ros,
        rootObject: viewer.scene
    });

    window.pane = function(a, b) {
        pan.startPan(a, b);
    }

    window.paned = function(c, d) {
        pan.pan(c, d);
    }

    window.zoomInMap = function(ros, viewer) {
        var zoom = new ROS2D.ZoomView({
            ros: ros,
            rootObject: viewer.scene
        });
        zoom.startZoom(250, 250);
        zoom.zoom(1.2);
    }

    window.zoomOutMap = function(ros, viewer) {
        var zoom = new ROS2D.ZoomView({
            ros: ros,
            rootObject: viewer.scene
        });
        zoom.startZoom(250, 250);
        zoom.zoom(0.8);
    }


    $("#home").click(function(event) {
        event.preventDefault();
        console.log("home button clicked");
        window.navigation = false;
        window.homing = true;
    });

    $("#navigate").click(function(event) {
        event.preventDefault();
        console.log("navigate button clicked");
        window.navigation = true;
        window.homing = false;
    });

    $('#path').change(function() {
        event.preventDefault();
        if (this.checked) {
            pathed();
        } else {
            upathed();
        }
    });
    $("#zoomplus").click(function(event) {
        event.preventDefault();
        zoomInMap(ros, viewer);

    });

    $("#zoomminus").click(function(event) {
        event.preventDefault();
        zoomOutMap(ros, viewer);

    });

    $("#maplive").click(function(event) {
        event.preventDefault();
        console.log("clicked");
        mapchangelive();

    });

    $("#mapgraphical").click(function(event) {
        event.preventDefault();
        console.log("clicked");
        mapchangegraphical();

    });
    $("#stop").click(function(event) {
        event.preventDefault();
        console.log("clicked");
        $.ajax({
            url: '/navigation/stop',
            type: 'POST',
            success: function(response) {
                console.log(response);
            },
            error: function(error) {
                console.log(error);
            }
        })
        upathed();

    });



    $('.menu-btn').click(function() {
        $(this).toggleClass("menu-btn-left");
        $('.box-out').toggleClass('box-in');
    });

    $("#startmap").click(function(event) {
        $body.addClass("loading");
        event.preventDefault();
        $.ajax({
            url: '/navigation/gotomapping',
            type: 'POST',
            success: function(response) {

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


    $(".close-navigation").click(function(event) {
        event.stopPropagation();
        $.ajax({
            url: '/navigation/deletemap',
            type: 'POST',
            data: event.target.previousSibling.data,
            success: function(response) {
                console.log(response);
            },
            error: function(error) {
                console.log(error);
            }
        })

    });

    var close = document.getElementsByClassName("close-navigation");
    var i;
    for (i = 0; i < close.length; i++) {
        close[i].onclick = function() {
            var div = this.parentElement;
            div.style.display = "none";
        }
    }



});

/* When the user clicks on the button,
toggle between hiding and showing the dropdown content */
function myFunction() {
    document.getElementById("drop-text").classList.toggle("show");
}

// Close the dropdown if the user clicks outside of it
window.onclick = function(e) {
    if (!e.target.matches('.dropbtn')) {
        var myDropdown = document.getElementById("drop-text");
        if (myDropdown.classList.contains('show')) {
            myDropdown.classList.remove('show');
        }
    }
}

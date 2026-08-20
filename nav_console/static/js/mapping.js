var navigation = false;
var pathed = false;
var homing = false;
var MAP_WIDTH = (window.innerWidth) * 0.65;
var MAP_HEIGHT = window.innerHeight - (window.innerHeight) * 0.08;
// See index.js for why this replaced the original rosout-message wait.
var STARTUP_DELAY_MS = 8000;

$(document).ready(function() {
    $body = $("body");
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



    var gridClient = new NAV2D.OccupancyGridClientNav({
        ros: ros,
        rootObject: viewer.scene,
        viewer: viewer,
        serverName: '/move_base',
        continuous: true
    });

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


    $("#zoomplus").click(function(event) {
        event.preventDefault();
        zoomInMap(ros, viewer);

    });

    $("#zoomminus").click(function(event) {
        event.preventDefault();
        zoomOutMap(ros, viewer);
    });

    $("#savemap").click(function(event) {
        event.preventDefault();



        var mapname = prompt("Please enter the name of the map");

        if (mapname) {
            $.ajax({
                url: '/mapping/savemap',
                type: 'POST',
                data: mapname,
                success: function(response) {
                    window.location = "/mapping";
                    console.log(response);
                },
                error: function(error) {
                    console.log(error);
                }

            })


        } else {
            alert("enter valid mapname to save");
        }

    });

    cmd_vel_listener = new ROSLIB.Topic({
        ros: ros,
        name: "/cmd_vel",
        messageType: 'geometry_msgs/Twist'
    });

    move = function(linear, angular) {
        var twist = new ROSLIB.Message({
            linear: {
                x: linear,
                y: 0,
                z: 0
            },
            angular: {
                x: 0,
                y: 0,
                z: angular
            }
        });
        cmd_vel_listener.publish(twist);
    }

    createJoystick = function() {
        var options = {
            zone: document.getElementById('zonejoystick'),
            threshold: 0.1,
            // Anchored at the CENTER of .joy-stick's zone, not '8%' from its
            // corner. That zone sits flush against the screen's right/bottom
            // edges (see main.css), so an anchor only 8% of the zone's own
            // width/height away from those edges left less than the
            // joystick's own 75px throw radius (below) between the knob and
            // the actual edge of the browser window - the mouse/finger ran
            // out of screen before the knob ran out of range, capping how
            // far right/down it could ever be dragged. Centering it gives
            // equal, ample clearance in every direction.
            position: { right: '50%', bottom: '50%' },
            mode: 'static',
            size: 150,
            color: 'blue',
        };
        manager = nipplejs.create(options);

        linear_speed = 0;
        angular_speed = 0;

        timer = setInterval(function() {
            move(linear_speed, angular_speed);
        }, 25);
        manager.on('start', function(event, nipple) {
            console.log("in start")
        });

        manager.on('move', function(event, nipple) {
            console.log("in move")
            // Matches the 0.3 m/s / 0.3 rad/s safety ceiling used
            // everywhere else in this project (web_teleop, DWA planner
            // limits) - was 0.4/0.8 in the original, inconsistent with that.
            max_linear = 0.3; // m/s
            max_angular = 0.3; // rad/s
            max_distance = 75.0; // pixels - matches size:150 above (radius)
            // nipple.js does not itself clamp nipple.distance to the drawn
            // circle's radius - drag past it and distance keeps growing, so
            // without this clamp full speed only landed exactly at 75px of
            // travel (easy to undershoot, capping the achievable speed well
            // below 0.3) while dragging further did nothing visually but
            // could still push the command past the 0.3 safety ceiling.
            // Clamping here means max speed is reached reliably right at the
            // visible edge of the knob's travel, same feel as web_teleop's
            // joystick (web_teleop/static/app.js), which clamps the same way.
            var distance = Math.min(nipple.distance, max_distance);
            linear_speed = Math.sin(nipple.angle.radian) * max_linear * distance / max_distance;
            angular_speed = -Math.cos(nipple.angle.radian) * max_angular * distance / max_distance;
        });

        manager.on('end', function() {
            console.log("in end")
            linear_speed = 0
            angular_speed = 0
        });
    }


    window.onload = function() {
        createJoystick();
    }

    $('.menu-btn').click(function() {
        $(this).toggleClass("menu-btn-left");
        $('.box-out').toggleClass('box-in');
    });


    $("#start-nav-button").click(function() {
        event.preventDefault();
    });

    $("#index-list-map").click(function(event) {

        document.cookie = event.target.innerHTML;
        $('#exampleModal').modal('hide');
        $.ajax({
            url: '/mapping/cutmapping',
            type: 'POST',
            success: function(response) {

                $.ajax({
                    url: '/index/navigation-precheck',
                    type: 'GET',
                    success: function(response) {
                        console.log(response.mapcount);
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

            },
            error: function(error) {
                console.log(error);
            }

        })

    });




});

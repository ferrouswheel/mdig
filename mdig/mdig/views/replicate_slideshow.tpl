<ul id="slideshow">
    <li>
        <h3>1990</h3>
        <span>/resources/orange-fish.jpg</span>
        <p></p>
        <a href="#"><img src="/resources/orange-fish-thumb.jpg" alt="Orange Fish" /></a>
    </li>
    <li>
        <h3>1991</h3>
        <span>/resources/sea-turtle.jpg</span>
        <p></p>
        <img src="/resources/sea-turtle-thumb.jpg" alt="Sea Turtle" />
    </li>
</ul>
<div id="wrapper">
    <div id="fullsize">
        <div id="imgprev" class="imgnav" title="Previous Image"></div>
        <div id="imglink"></div>
        <div id="imgnext" class="imgnav" title="Next Image"></div>
        <div id="image"></div>
        <div id="information">
            <h3></h3>
            <p></p>
        </div>
    </div>
    <!--<div id="thumbnails">
        <div id="slideleft" title="Slide Left"></div>

        <div id="slidearea">
            <div id="slider"></div>
        </div>
        <div id="slideright" title="Slide Right"></div>
    </div>-->
</div>
<script type="text/javascript" src="/resources/compressed.js"></script>
<script type="text/javascript">
    $('slideshow').style.display='none';
    $('wrapper').style.display='block';
    var slideshow=new TINY.slideshow("slideshow");
    window.onload=function(){
        slideshow.auto=false;
        slideshow.link="linkhover";
        slideshow.info="information";
        //slideshow.thumbs="slider";
        slideshow.left="slideleft";
        slideshow.right="slideright";
        slideshow.scrollSpeed=9;
        slideshow.spacing=5;
        slideshow.active="#fff";
        slideshow.init("slideshow","image","imgprev","imgnext","imglink");
    }
</script>


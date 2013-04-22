"use strict";

$(document).ready(function () {
	$('#col section .inner').not(':first-child').hide();
	$('#col section header').click(function(){
		$(this).siblings('.inner').slideToggle();
	});
	$('.project-card .hover').hide();
	$('.project-card').hover(function(){
		$(this).children('.hover').fadeIn(100);
	},function(){
		$(this).children('.hover').fadeOut(100);
	});
});


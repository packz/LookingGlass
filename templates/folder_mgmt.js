
$('.new-folder').click(function(){
  $('#new-folder-input').fadeIn();
  $('#new-folder-input').focus();
});

function new_folder_named() {
  $('#new-folder-input').fadeOut();
  if ($('#new-folder-input').length > 0) {
    $('#destFolder').val($('#new-folder-input').val());
    $('#msgForm').attr('action','{% url 'emailclient.create_folder' %}');
    $('#msgForm').submit();
  }
}

$('#new-folder-input').keypress(function(e){
  if (e.which == 13) {
    $('#new-folder-input').blur();
  };
});

$('#new-folder-input').blur(function(){
  new_folder_named();
});


$('#trash-folder').click(function(){
  if (confirm('Delete folder and trash ALL messages?')) {
    $.post('{% url 'emailclient.delete_folder' %}',
	   {'folderName':$(this).data('foldername'),
	    'csrfmiddlewaretoken':'{{ csrf_token }}',
	   },
	   function(data) {
	     if (data.ok) {
	       location.assign('{% url 'emailclient.inbox' %}');
	     };
	   }, 'json');
  };
});

$('.move-folder').click(function() {
  $('#destFolder').val($(this).data('foldername'));
  $('#msgForm').attr('action','{% url 'emailclient.move' %}');
  $('#msgForm').submit();
});

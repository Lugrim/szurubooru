<div class='content-wrapper' id='settings'>
    <form>
        <strong>Browsing settings</strong>
        <p>These settings are saved to the browser's local storage and are not coupled to the user account, so they don't apply to other devices or browsers alike.</p>
        <div class='input'>
            <ul>
                <li>
                    <%= makeCheckbox({text: 'Endless scroll', id: 'endless-scroll', name: 'endless-scroll', checked: browsingSettings.endlessScroll}) %>
                    <p class='hint'>Rather than using a paged navigation, smoothly scroll through the content.</p>
                </li>
                <li>
                    <%= makeCheckbox({text: 'Enable keyboard shortcuts', id: 'keyboard-shortcuts', name: 'keyboard-shortcuts', checked: browsingSettings.keyboardShortcuts}) %>
                    <a class='append icon' href='/help/keyboard'><i class='fa fa-question-circle-o'></i></a>
                </li>
            </ul>
        </div>
        <div class='messages'></div>
        <div class='buttons'>
            <input type='submit' value='Save settings'/>
        </div>
    </form>
</div>